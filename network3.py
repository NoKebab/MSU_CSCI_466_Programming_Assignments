"""
Created on Oct 12, 2016

@author: mwittie
"""
import queue
import threading
from rprint import print


# wrapper class for a queue of packets
class Interface:
    # @param max_queue_size - the maximum size of the queue storing packets
    #  @param mtu - the maximum transmission unit on this interface
    def __init__(self, max_queue_size=0):
        self.queue = queue.Queue(max_queue_size)
        self.mtu = 1

    # get packet from the queue interface
    def get(self):
        try:
            return self.queue.get(False)
        except queue.Empty:
            return None

    # put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, block=False):
        self.queue.put(pkt, block)


# Implements a network layer packet (different from the RDT packet
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    # packet encoding lengths
    ident_length = 2
    dst_addr_S_length = 5
    flag_length = 1
    offset_length = 2
    # total length
    header_length = dst_addr_S_length + flag_length + ident_length + offset_length

    # @param dst_addr: address of the destination host
    # @param data_S: packet payload
    def __init__(self, dst_addr, data_S, ident_num=1, frag_flag=0, offset=0):
        # added fields for segmentation:
        # allows destination to distinguish between fragments of different packets
        self.ident_num = ident_num
        # marks whether the packet is a fragment '1' or end of fragment/whole message '0'
        self.frag_flag = frag_flag
        # start position of data in fragment used to reassemble packets regardless of in order arrival
        self.offset = offset
        self.dst_addr = dst_addr
        self.data_S = data_S

    # called when printing the object
    def __str__(self):
        return self.to_byte_S()

    # convert packet to a byte string for transmission over links
    def to_byte_S(self):
        # update for new packet fields
        byte_S = str(self.ident_num).zfill(self.ident_length)
        byte_S += str(self.frag_flag).zfill(self.flag_length)
        byte_S += str(self.offset).zfill(self.offset_length)
        byte_S += str(self.dst_addr).zfill(self.dst_addr_S_length)
        byte_S += self.data_S
        return byte_S

    # extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        # added segmentation functionality fields
        ident_num = int(byte_S[:NetworkPacket.ident_length])
        marker = NetworkPacket.ident_length
        frag_flag = int(byte_S[marker: marker + NetworkPacket.flag_length])
        marker += NetworkPacket.flag_length
        offset = int(byte_S[marker: marker + NetworkPacket.offset_length])
        marker += NetworkPacket.offset_length
        dst_addr = int(byte_S[marker: marker + NetworkPacket.dst_addr_S_length])
        marker += NetworkPacket.dst_addr_S_length
        data_S = byte_S[marker:]
        return self(dst_addr, data_S, ident_num, frag_flag, offset)


# Implements a network host for receiving and transmitting data
class Host:
    # @param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.in_intf_L = [Interface()]
        self.out_intf_L = [Interface()]
        self.stop = False  # for thread termination
        # added fragmented packets list
        self.fragments = []

    # called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)

    # split the packet up into multiple segments if the length exceeds the mtu of the out link recursively
    def segment(self, packet, mtu):
        # total packet length
        length = NetworkPacket.header_length + len(packet.data_S)
        header_length = NetworkPacket.header_length
        offset = packet.offset
        # end of the slice of the data_S that can fit in the mtu
        seg_msg_length = offset + mtu - header_length
        if length > mtu:
            # calculate whether the packet is the final segment or first
            flag = int(length > mtu * 2)
            # create segment
            p = NetworkPacket(packet.dst_addr, packet.data_S[offset:seg_msg_length], packet.ident_num, flag, offset)
            print('%s: sending packet "%s" on the out interface with mtu=%d' % (self, p, mtu))
            self.out_intf_L[0].put(p.to_byte_S())
            packet.data_S = packet.data_S[offset:]
            new_offset = seg_msg_length - offset
            packet.offset = new_offset
            self.segment(packet, mtu)

    # create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S, ident):
        # split the packet up into multiple segments if the length exceeds the mtu of the out link
        mtu = self.out_intf_L[0].mtu
        if len(data_S) + NetworkPacket.header_length > mtu:
            p = NetworkPacket(dst_addr, data_S, ident, frag_flag=0, offset=0)
            self.segment(p, mtu)
        else:
            p = NetworkPacket(dst_addr, data_S, ident, frag_flag=0, offset=0)
            self.out_intf_L[0].put(p.to_byte_S())


    # receive packet from the network layer and reconstruct fragmented packets
    # host 2 receives
    def udt_receive(self):
        pkt_S = self.in_intf_L[0].get()
        if pkt_S is not None:
            p = NetworkPacket.from_byte_S(pkt_S)
            self.fragments.append(p)
            if p.frag_flag == 0:
                # reassemble packet if end of fragments reached
                msg = ''
                for fragment in self.fragments:
                    # string together the right messages
                    if fragment.ident_num == p.ident_num:
                        msg += fragment.data_S
                print('%s: received packet "%s" on the in interface' % (self, msg))

    # thread target for the host to keep receiving data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            # receive data arriving to the in interface
            self.udt_receive()
            # terminate
            if (self.stop):
                print(threading.currentThread().getName() + ': Ending')
                return


# Implements a multi-interface router described in class
class Router:

    # @param name: friendly router name for debugging
    # @param intf_count: the number of input and output interfaces
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_count, max_queue_size, routing_table):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.routing_table = routing_table

    # called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    # split the packet up into multiple segments if the length exceeds the mtu of the out link recursively
    def fragment(self, packet, in_intf, out, mtu, offset=0):
        header_length = NetworkPacket.header_length
        length = header_length + len(packet.data_S)
        seg_msg_length = offset + mtu - header_length
        if length > mtu:
            p = NetworkPacket(packet.dst_addr, packet.data_S[offset:seg_msg_length], packet.ident_num, 1, offset=offset)
            print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' % (self, p, in_intf, out, mtu))
            self.out_intf_L[out].put(p.to_byte_S())
            offset = seg_msg_length - offset
            packet.data_S = packet.data_S[offset:]
            self.fragment(packet, in_intf, out, mtu, offset)
        else:
            print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' % (self, packet, in_intf, out, mtu))
            self.out_intf_L[out].put(packet.to_byte_S())

    # look through the content of incoming interfaces and forward to
    # appropriate outgoing interfaces
    def forward(self):
        for i in range(len(self.in_intf_L)):
            pkt_S = None
            try:
                # get packet from interface i
                pkt_S = self.in_intf_L[i].get()
                # if packet exists make a forwarding decision
                if pkt_S is not None:
                    # print('\nMade it to Forward w/ non empty packet\n')
                    p = NetworkPacket.from_byte_S(pkt_S)  # parse a packet out
                    # HERE you will need to implement a lookup into the
                    # forwarding table to find the appropriate outgoing interface
                    # for now we assume the outgoing interface is also i
                    out = self.routing_table.get(p.dst_addr)
                    mtu = self.out_intf_L[out].mtu
                    # fragment packet if necessary and forward it to corresponding out interface
                    self.fragment(p, i, out, mtu)
            except queue.Full:
                print('%s: packet "%s" lost on interface %d' % (self, p, i))
                pass

    # thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.forward()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return
