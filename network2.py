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
    dst_addr_S_length = 5
    flag_length = 1
    ident_length = 1
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

    def segment(self, dst_addr, data_S):
        # split the packet up into multiple segments if the length exceeds the mtu of the out link
        mtu = self.out_intf_L[0].mtu
        header_length = NetworkPacket.header_length
        length = len(data_S) + header_length
        offset = 0
        # partition packet
        while length > mtu:
            # signal end of segment
            flag = int(length > mtu * 2)
            p = NetworkPacket(dst_addr, data_S[offset:offset + mtu - header_length], frag_flag=flag, offset=offset)
            print('%s: sending packet "%s" on the out interface with mtu=%d\n' % (self, p, mtu))
            self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully
            offset += mtu - header_length
            length -= mtu
        # send out last segment or an unsegmented packet smaller than mtu
        p = NetworkPacket(dst_addr, data_S[offset:], frag_flag=0, offset=offset)
        print('%s: sending packet "%s" on the out interface with mtu=%d\n' % (self, p, mtu))
        self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully
    # create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        # split the packet up into multiple segments if the length exceeds the mtu of the out link
        mtu = self.out_intf_L[0].mtu
        header_length = NetworkPacket.header_length
        length = len(data_S) + header_length
        offset = 0
        # partition packet
        while length > mtu:
            # signal end of segment
            flag = int(length > mtu * 2)
            p = NetworkPacket(dst_addr, data_S[offset:offset + mtu - header_length], frag_flag=flag, offset=offset)
            print('%s: sending packet "%s" on the out interface with mtu=%d\n' % (self, p, mtu))
            self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully
            offset += mtu - header_length
            length -= mtu
        # send out last segment or an unsegmented packet smaller than mtu
        p = NetworkPacket(dst_addr, data_S[offset:], frag_flag=0, offset=offset)
        print('%s: sending packet "%s" on the out interface with mtu=%d\n' % (self, p, mtu))
        self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully

    # receive packet from the network layer and reconstruct fragmented packets
    def udt_receive(self):
        pkt_S = self.in_intf_L[0].get()
        if pkt_S is not None:
            p = NetworkPacket.from_byte_S(pkt_S)
            self.fragments.append(pkt_S[NetworkPacket.header_length:])
            if not p.frag_flag:  # i.e. flag is 0
                print('%s: received packet "%s" on the in interface' % (self, str(self.fragments)))
                self.fragments = []

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
    def __init__(self, name, intf_count, max_queue_size):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]

    # called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

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
                    p = NetworkPacket.from_byte_S(pkt_S)  # parse a packet out
                    mtu = self.out_intf_L[i].mtu
                    # length = len(pkt_S)
                    # if length > 50:
                    #     p1 = NetworkPacket(p.dst_addr, p.data_S[:length // 2])
                    #     print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' % (self, p1, i, i, mtu))
                    #     self.out_intf_L[i].put(p1.to_byte_S())  # send packets always enqueued successfully
                    #
                    #     p2 = NetworkPacket(p.dst_addr, p.data_S[length // 2:])
                    #     print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' % (self, p2, i, i, mtu))
                    #     self.out_intf_L[i].put(p2.to_byte_S())  # send packets always enqueued successfully
                    # else:
                    # HERE you will need to implement a lookup into the
                    # forwarding table to find the appropriate outgoing interface
                    # for now we assume the outgoing interface is also i
                    print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' % (self, p, i, i, mtu))
                    self.out_intf_L[i].put(p.to_byte_S())
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
