from datetime import datetime, timedelta
import Network
import argparse
from time import sleep
import hashlib


class RDTException(Exception):
    pass


class Packet:
    # the number of bytes used to store packet length
    seq_num_S_length = 10
    length_S_length = 10
    # length of md5 checksum in hex
    checksum_length = 32

    def __init__(self, seq_num, msg_S):
        self.seq_num = seq_num
        self.msg_S = msg_S

    @classmethod
    def from_byte_S(cls, byte_S):
        if Packet.corrupt(byte_S):
            raise RuntimeError('Cannot initialize Packet: byte_S is corrupt')
        # extract the fields
        seq_num = int(byte_S[Packet.length_S_length: Packet.length_S_length + Packet.seq_num_S_length])
        msg_S = byte_S[Packet.length_S_length + Packet.seq_num_S_length + Packet.checksum_length:]
        return cls(seq_num, msg_S)

    def get_byte_S(self):
        # convert sequence number of a byte field of seq_num_S_length bytes
        seq_num_S = str(self.seq_num).zfill(self.seq_num_S_length)
        # convert length to a byte field of length_S_length bytes
        length_S = str(self.length_S_length + len(seq_num_S) + self.checksum_length + len(self.msg_S)).zfill(
            self.length_S_length)
        # compute the checksum
        checksum = hashlib.md5((length_S + seq_num_S + self.msg_S).encode('utf-8'))
        checksum_S = checksum.hexdigest()
        # compile into a string
        return length_S + seq_num_S + checksum_S + self.msg_S

    @staticmethod
    def corrupt(byte_S):
        # extract the fields
        length_S = byte_S[0:Packet.length_S_length]
        seq_num_S = byte_S[Packet.length_S_length: Packet.length_S_length + Packet.seq_num_S_length]
        checksum_S = byte_S[
                     Packet.length_S_length + Packet.seq_num_S_length: Packet.length_S_length + Packet.seq_num_S_length + Packet.checksum_length]
        msg_S = byte_S[Packet.length_S_length + Packet.seq_num_S_length + Packet.checksum_length:]

        # compute the checksum locally
        checksum = hashlib.md5(str(length_S + seq_num_S + msg_S).encode('utf-8'))
        computed_checksum_S = checksum.hexdigest()
        # and check if the same
        return checksum_S != computed_checksum_S


class RDT:
    # receive timeout
    timeout = timedelta(seconds=2)
    # latest sequence number used in a packet
    seq_num = 0
    # buffer of bytes read from network
    byte_buffer = ''
    # additional buffer for ACKs
    receiver_buffer = ''

    def __init__(self, role_S, server_S, port):
        # use the passed in port and port+1 to set up unidirectional links between
        # RDT send and receive functions
        # cross the ports on the client and server to match net_snd to net_rcv
        if role_S == 'server':
            self.net_snd = Network.NetworkLayer(role_S, server_S, port)
            self.net_rcv = Network.NetworkLayer(role_S, server_S, port + 1)
        else:
            self.net_rcv = Network.NetworkLayer(role_S, server_S, port)
            self.net_snd = Network.NetworkLayer(role_S, server_S, port + 1)

    def disconnect(self):
        self.net_snd.disconnect()
        del self.net_snd
        self.net_rcv.disconnect()
        del self.net_rcv

    def rdt_1_0_send(self, msg_S):
        p = Packet(self.seq_num, msg_S)
        self.seq_num += 1
        # !!! make sure to use net_snd link to udt_send and udt_receive in the RDT send function
        self.net_snd.udt_send(p.get_byte_S())

    def rdt_1_0_receive(self):
        start = datetime.now()
        while True:
            if datetime.now() - start > self.timeout:
                raise RDTException("timeout")
            # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
            byte_S = self.net_rcv.udt_receive()
            self.byte_buffer += byte_S
            # check if we have received enough bytes
            if len(self.byte_buffer) < Packet.length_S_length:
                # return ret_S  # not enough bytes to read packet length
                continue
            # extract length of packet
            length = int(self.byte_buffer[:Packet.length_S_length])
            if len(self.byte_buffer) < length:
                # return ret_S  # not enough bytes to read the whole packet
                continue
            # create packet from buffer content
            p = Packet.from_byte_S(self.byte_buffer[0:length])
            # remove the packet bytes from the buffer
            self.byte_buffer = self.byte_buffer[length:]
            # return packet message to the upper layer
            return p.msg_S

    # Implement These:

    # helper gets input from the receiver to the sender
    # returns the byte stream sent from receiver
    def __receive_helper(self):
        # print('Made it to receive helper')
        start = datetime.now()
        while True:
            if datetime.now() - start > self.timeout:
                return
                # raise RDTException("timeout")
            # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
            byte_S = self.net_snd.udt_receive()
            self.receiver_buffer += byte_S
            # check if we have received enough bytes
            if len(self.receiver_buffer) < Packet.length_S_length:
                # return ret_S  # not enough bytes to read packet length
                continue
            # extract length of packet
            length = int(self.receiver_buffer[:Packet.length_S_length])
            if len(self.receiver_buffer) < length:
                # return ret_S  # not enough bytes to read the whole packet
                continue
            # remove the packet bytes from the buffer
            # print('Receive helper byte stream: ', self.receiver_buffer)
            temp = self.receiver_buffer
            self.receiver_buffer = self.receiver_buffer[length:]
            return temp[0:length]

    # rdt 1.0 send + corruption and duplicate
    def rdt_2_1_send(self, msg_S):
        # State 1: Wait for call 0 from above
        snd_packet = Packet(self.seq_num, msg_S)
        self.seq_num = 0
        while True:
            self.byte_buffer = ''
            self.net_snd.udt_send(snd_packet.get_byte_S())
            # State 2: STOP AND WAIT for an ACK or NAK after transmitting packet
            rcv = self.__receive_helper()
            if rcv is None:
                return
            if Packet.corrupt(rcv):
                print('ACK or NAK Packet Corrupt')
                # increment packet seq num for retransmit
                snd_packet = Packet(self.seq_num + 1, msg_S)
                self.net_snd.udt_send(snd_packet.get_byte_S())
                return
            snd_packet = Packet(self.seq_num, msg_S)
            rcv_packet = Packet.from_byte_S(rcv)
            if rcv_packet.msg_S == 'NAK':
                print('NAK received in sender')
                continue
            print('ACK received in sender')
            # self.seq_num += 1
            break
        # Transition to mirror image of first two states

    def rdt_2_1_receive(self):
        start = datetime.now()
        while True:
            if datetime.now() - start > self.timeout:
                raise RDTException("timeout")
            # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
            byte_S = self.net_rcv.udt_receive()
            self.byte_buffer += byte_S
            # check if we have received enough bytes
            if len(self.byte_buffer) < Packet.length_S_length:
                # return ret_S  # not enough bytes to read packet length
                continue
            # extract length of packet
            length = int(self.byte_buffer[:Packet.length_S_length])
            if len(self.byte_buffer) < length:
                # return ret_S  # not enough bytes to read the whole packet
                continue
            # State 1 loop transitions
            # print('Packet: %s' % self.byte_buffer)
            if Packet.corrupt(self.byte_buffer):
                print('Corrupt packet sent to receiver')
                self.byte_buffer = self.byte_buffer[length:]
                nak = Packet(self.seq_num, 'NAK')
                self.net_rcv.udt_send(nak.get_byte_S())
                continue
                # self.receiver_buffer += nak.get_byte_S()
            # IMPORTANT: pulls the bytes from buffer
            # create packet from buffer content
            p = Packet.from_byte_S(self.byte_buffer[0:length])
            # print('Receiver seq num: ', p.seq_num)
            ack = Packet(self.seq_num, 'ACK')
            self.net_rcv.udt_send(ack.get_byte_S())
            # duplicate
            if p.seq_num > self.seq_num:
                print('Retransmit received')
                # remove the packet bytes from the buffer
                self.byte_buffer = self.byte_buffer[length:]
                continue
            # remove the packet bytes from the buffer
            self.byte_buffer = self.byte_buffer[length:]
            # return packet message to the upper layer
            return p.msg_S

    def __receive_helper3_0(self, timer):
        # print('Made it to receive helper')
        # start = datetime.now()
        while True:
            if datetime.now() - timer > self.timeout:
                return 'timeout'
                # raise RDTException("timeout")
            # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
            byte_S = self.net_snd.udt_receive()
            self.receiver_buffer += byte_S
            if self.receiver_buffer == 'timeout':
                return byte_S
                # check if we have received enough bytes
            if len(self.receiver_buffer) < Packet.length_S_length:
                # return ret_S  # not enough bytes to read packet length
                continue
            # extract length of packet
            length = int(self.receiver_buffer[:Packet.length_S_length])
            if len(self.receiver_buffer) < length:
                # return ret_S  # not enough bytes to read the whole packet
                continue
            # remove the packet bytes from the buffer
            # print('Receive helper byte stream: ', self.receiver_buffer)
            temp = self.receiver_buffer
            self.receiver_buffer = self.receiver_buffer[length:]
            return temp[0:length]

    def rdt_3_0_send(self, msg_S):
        # State 1: Wait for call 0 from above
        snd_packet = Packet(self.seq_num, msg_S)
        self.seq_num = 0
        while True:
            self.byte_buffer = ''
            self.net_snd.udt_send(snd_packet.get_byte_S())
            # the important change from 2_1
            # start timer
            timer = datetime.now()
            # State 2: STOP AND WAIT for an ACK or NAK after transmitting packet
            rcv = self.__receive_helper3_0(timer)
            if rcv is None or rcv == '':
                self.byte_buffer = ''
                self.receiver_buffer = ''
                return
            if rcv == 'timeout':
                print('Retransmit after timeout')
                self.byte_buffer = ''
                self.receiver_buffer = ''
                # self.net_snd.udt_send(snd_packet.get_byte_S())
                return
            if Packet.corrupt(rcv):
                # print('ACK or NAK Packet Corrupt')
                # increment packet seq num for retransmit
                self.receiver_buffer = ''
                # snd_packet = Packet(self.seq_num + 1, msg_S)
                # self.net_snd.udt_send(snd_packet.get_byte_S())
                return
            snd_packet = Packet(self.seq_num, msg_S)
            rcv_packet = Packet.from_byte_S(rcv)
            if rcv_packet.msg_S == 'NAK':
                # print('NAK received in sender')
                continue
            # print('ACK received in sender')
            # self.seq_num += 1
            # stop timer
            break
        # Transition to mirror image of first two states

    def rdt_3_0_receive(self):
        start = datetime.now()
        while True:
            if datetime.now() - start > self.timeout:
                # return
                p = Packet(0, 'timeout')
                self.net_rcv.udt_send(p.get_byte_S())
                # return
                raise RDTException("timeout")
            # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
            byte_S = self.net_rcv.udt_receive()
            self.byte_buffer += byte_S
            # check if we have received enough bytes
            if len(self.byte_buffer) < Packet.length_S_length:
                # return ret_S  # not enough bytes to read packet length
                continue
            # extract length of packet
            length = int(self.byte_buffer[:Packet.length_S_length])
            if len(self.byte_buffer) < length:
                # return ret_S  # not enough bytes to read the whole packet
                continue
            # State 1 loop transitions
            # print('Packet: %s' % self.byte_buffer)
            if Packet.corrupt(self.byte_buffer):
                # print('Corrupt packet sent to receiver')
                self.byte_buffer = self.byte_buffer[length:]
                nak = Packet(self.seq_num, 'NAK')
                self.net_rcv.udt_send(nak.get_byte_S())
                continue
                # self.receiver_buffer += nak.get_byte_S()
            # IMPORTANT: pulls the bytes from buffer
            # create packet from buffer content
            p = Packet.from_byte_S(self.byte_buffer[0:length])
            # print('Receiver seq num: ', p.seq_num)
            ack = Packet(self.seq_num, 'ACK')
            self.net_rcv.udt_send(ack.get_byte_S())
            # duplicate
            if p.seq_num > self.seq_num:
                # print('Retransmit received')
                # remove the packet bytes from the buffer
                self.byte_buffer = self.byte_buffer[length:]
                self.receiver_buffer = ''
                return
            # remove the packet bytes from the buffer
            self.byte_buffer = self.byte_buffer[length:]
            # return packet message to the upper layer
            return p.msg_S


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RDT implementation.')
    parser.add_argument('role', help='Role is either client or server.', choices=['client', 'server'])
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    rdt = RDT(args.role, args.server, args.port)
    if args.role == 'client':
        rdt.rdt_3_0_send('MSG_FROM_CLIENT')
        sleep(2)
        print(rdt.rdt_3_0_receive())
        rdt.disconnect()
    else:
        sleep(1)
        print(rdt.rdt_3_0_receive())
        rdt.rdt_3_0_send('MSG_FROM_SERVER')
        rdt.disconnect()
