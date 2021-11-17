import queue
import threading
import json
import copy
from rprint import print
from time import sleep


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)

    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)


## Implements a network layer packet.
class NetworkPacket:
    ## packet encoding lengths 
    dst_S_length = 5
    prot_S_length = 1

    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise ('%s: unknown prot_S option: %s' % (self, self.prot_S))
        byte_S += self.data_S
        return byte_S

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0: NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length: NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise ('%s: unknown prot_S field: %s' % (self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length:]
        return self(dst, prot_S, data_S)


## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False  # for thread termination

    ## called when printing the object
    def __str__(self):
        return self.addr

    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out')  # send packets always enqueued successfully

    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))

    ## thread target for the host to keep receiving data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            # receive data arriving to the in interface
            self.udt_receive()
            # terminate
            if (self.stop):
                print(threading.currentThread().getName() + ': Ending')
                return


## Implements a multi-interface router
class Router:

    ##@param name: friendly router name for debugging
    # @param cost_D: cost table to neighbors {neighbor: {interface: cost}}
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.intf_L = [Interface(max_queue_size) for _ in range(len(cost_D))]
        # save neighbors and interfeces on which we connect to them
        self.cost_D = cost_D  # {neighbor: {interface: cost}}
        # TODO: set up the routing table for connected hosts
        self.rt_tbl_D = self.initializeRTable(self.cost_D)  # {destination: {router: cost}}
        # if self.name == 'RC': self.rt_tbl_D.clear()
        # if self.name == 'RB': self.rt_tbl_D.clear()
        # if self.name == 'RA': self.rt_tbl_D.clear()
        # if self.name == 'RD': self.rt_tbl_D.clear()
        self.frwdTbl = []
        self.calculatedTable = copy.deepcopy(self.rt_tbl_D)
        print('%s: Initialized routing table' % self)
        self.print_routes()

    def convertToList(self):  # CONVERTS RT_TBL TO INDIVIDUAL DICTIONARIES IN A LIST
        items = []
        tmp = copy.deepcopy(self.rt_tbl_D)
        for key, val in tmp.items():
            while len(val) > 0:
                valKey = list(val.keys())
                items.append({key: {valKey[0]: val.pop(valKey[0])}})
        return items

    def formatFtable(self):
        duplicates = []
        recurse = True
        for q in range(len(self.frwdTbl)):
            x = list(self.frwdTbl[q].values())[0]
            Qkey = list(x.keys())[0]
            qval = x.get(Qkey)
            qRtr = list(qval.keys())[0]
            qCost = qval.get(qRtr)
            for i in range(len(self.frwdTbl)):
                y = list(self.frwdTbl[i].values())[0]
                iKey = list(y.keys())[0]
                iVal = y.get(iKey)
                iRtr = list(iVal.keys())[0]
                iCost = iVal.get(iRtr)

                if Qkey == iKey and qRtr == iRtr and iCost > qCost:
                    duplicates.append(self.frwdTbl[i])
        if len(duplicates) == 0: recurse = False
        for i in range(len(duplicates)):
            try:
                self.frwdTbl.remove(duplicates[i])
            except ValueError:
                pass

        res = []
        [res.append(x) for x in self.frwdTbl if x not in res]
        self.frwdTbl = res
        if recurse:
            self.formatFtable()

    def CalcDist(self, sList):  # sList is items list returned from convertToList()
        calculatedRoutes = []
        for q in range(len(sList)):
            Qkey = list(sList[q].keys())[0]
            Qval = list(sList[q].values())[0]
            Qrouter = list(Qval.keys())[0]
            Qcost = Qval.get(Qrouter)
            qList = [Qkey, Qval, Qrouter, Qcost]
            for i in range(len(sList)):
                iKey = list(sList[i].keys())[0]
                iVal = list(sList[i].values())[0]
                iRtr = list(iVal.keys())[0]
                iCost = iVal.get(iRtr)
                iList = [iKey, iVal, iRtr, iCost]

                self.updateIntf(qList, iList)

                if Qkey == iRtr and iKey != Qrouter:
                    calculatedRoutes.append({iKey: {Qrouter: Qcost + iCost}})
        return calculatedRoutes

    def updateIntf(self, qList, iList):
        # [0] = key , [1] = val , [2] = router , [3] = cost
        Qkey, Qval, Qrouter, Qcost = qList[0], qList[1], qList[2], qList[3]
        iKey, iVal, iRtr, iCost = iList[0], iList[1], iList[2], iList[3]

        if Qrouter == self.name and Qkey in self.cost_D.keys():
            intf = self.cost_D.get(Qkey)
            intf = list(intf.keys())[0]
            frwdItem = {intf: {Qkey: {Qrouter: Qcost}}}
            if frwdItem not in self.frwdTbl:
                self.frwdTbl.append(frwdItem)

        if Qkey == iRtr and iKey != Qrouter and Qrouter == self.name:
            status = self.checkFrwdList(iKey, Qrouter)  # if exists in frwdList then return items
            if status and Qkey in self.cost_D.keys():
                intf = self.cost_D.get(Qkey)
                intf = list(intf.keys())[0]
                self.frwdTbl.append({intf: {iKey: {Qrouter: Qcost + iCost}}})
            elif isinstance(status, list):  # POSSIBLE ISSUE WITH IF STATUS
                for i in range(len(status)):
                    intf = list(status[i].keys())[0]
                    x = list(status[i].values())[0]
                    key = list(x.keys())[0]
                    val = x.get(key)
                    rtr = list(val.keys())[0]
                    cost = val.get(rtr)
                    self.frwdTbl.append({intf: {iKey: {Qrouter: Qcost + cost}}})

    def checkFrwdList(self, a, b):
        matches = []
        if len(self.frwdTbl) == 0: return True
        for i in range(len(self.frwdTbl)):
            x = list(self.frwdTbl[i].values())[0]
            key = list(x.keys())[0]
            val = x.get(key)
            rtr = list(val.keys())[0]
            cost = val.get(rtr)

            if key == a and rtr == b:
                matches.append(self.frwdTbl[i])
        if len(matches) > 0:
            return matches
        else:
            return True

    def updateList(self, calculatedRoutes, sList):
        duplicates = []
        for q in range(len(calculatedRoutes)):  # MARK HIGHER COST PATHS (FOR REMOVAL)
            Qkey = list(calculatedRoutes[q].keys())[0]
            Qval = list(calculatedRoutes[q].values())[0]
            Qrouter = list(Qval.keys())[0]
            Qcost = Qval.get(Qrouter)
            for i in range(len(calculatedRoutes)):
                iKey = list(calculatedRoutes[i].keys())[0]
                iVal = list(calculatedRoutes[i].values())[0]
                iRtr = list(iVal.keys())[0]
                iCost = iVal.get(iRtr)

                if Qkey == iKey and Qrouter == iRtr and iCost > Qcost:
                    duplicates.append(calculatedRoutes[i])

        for i in range(len(duplicates)):  # REMOVE DUPLICATES
            try:
                calculatedRoutes.remove(duplicates[i])
            except ValueError:
                pass

        calculatedRoutes.extend(sList)
        res = []
        [res.append(x) for x in calculatedRoutes if x not in res]
        return res

    def convergeTable(self, table, hist):
        x = self.CalcDist(table)
        x = self.updateList(x, self.convertToList())
        hist.append(len(x))
        if len(hist) > 1 and hist[-1] == hist[-2]:
            x = self.updateList(x, self.convertToList())
            return x
        return self.convergeTable(x, hist)

    def listToDict(self, x):
        self.calculatedTable.clear()
        for i in range(len(x)):
            for key, val in x[i].items():
                if key in self.calculatedTable.keys():
                    self.calculatedTable.get(key).update(val)
                else:
                    self.calculatedTable.update({key: val})

    def appendTables(self, p):  # MERGES PACKET dict RECEIVED with self.rt_Tbl
        for key, val in p.items():
            if key in self.rt_tbl_D.keys():
                self.rt_tbl_D.get(key).update(val)
            else:
                self.rt_tbl_D.update({key: val})

    def initializeRTable(self, costTable):  # CREATES INITIAL ROUTING TABLE WHEN ROUTER IS CREATED
        rt_tbl = {self.name: {self.name: 0}}
        # rt_tbl = {}
        costDict = {}
        dstList = list(costTable.keys())
        for item in costTable.values():
            costDict.update(item)
        costList = list(costDict.values())
        for i in range(len(costTable)):
            rt_tbl[dstList[i]] = {self.name: costList[i]}
        return rt_tbl

    ## Print routing table
    # def print_routes(self):
    #     #TODO: print the routes as a two dimensional table
    #
    #     print(self.name+' CONVERGED: ',self.calculatedTable)
    #     print(self.name+' COMPLETED: ', self.rt_tbl_D)

    def print_routes(self):
        # TODO: print the routes as a two dimensional table
        for _ in range(len(self.calculatedTable)):
            print(end="+----")
        print('+')
        print(self.name, end="| ")
        # print known destinations
        destinations = []
        for destination in self.calculatedTable:
            destinations.append(destination)
        # align destinations for printing
        destinations.sort()
        for destination in destinations:
            print(destination, end="| ")
        print()
        # print known routers with cost associations
        # prevents printing the router every time we get the cost
        printed_routers = []
        # find all routers and sort
        router_list = []
        for dest in destinations:
            for routers in self.calculatedTable.get(dest).keys():
                router_list.append(routers)
            # routers should stay the same across destinations so only need to gather them once
            break
        router_list.sort()
        # find associated cost with routers
        costs = {}
        for dest in destinations:
            for router, cost in self.calculatedTable.get(dest).items():
                if costs.get(router) is None:
                    costs[router] = [cost]
                else:
                    costs.get(router).append(cost)
        # sort the keys
        sorted_costs = {}
        for i in sorted(costs):
            sorted_costs[i] = costs[i]

        for router in sorted_costs:
            print(router, end='| ')
            for cost in sorted_costs.get(router):
                print(cost, end=' | ')
            print()
        for _ in range(len(self.calculatedTable)):
            print(end="+----")
        print('+')
        # print(self.calculatedTable)

    ## called when printing the object
    def __str__(self):
        return self.name

    ## look through the content of incoming interfaces and
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            # get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            # if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S)  # parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p, i)
                elif p.prot_S == 'control':
                    self.update_routes(p, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            # TODO: Here you will need to implement a lookup into the 
            # forwarding table to find the appropriate outgoing interface
            # for now we assume the outgoing interface is 1
            interface = 1
            length = NetworkPacket.dst_S_length
            p1 = str(p)
            dst = p1[:length]
            dst = dst.lstrip("0")

            for j in range(len(self.frwdTbl)):
                intf = list(self.frwdTbl[j].keys())[0]
                x = list(self.frwdTbl[j].values())[0]
                key = list(x.keys())[0]
                if dst == key:
                    interface = intf

            self.intf_L[interface].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                  (self, p, i, interface))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        # TODO: Send out a routing table update
        # create a routing table update packet
        p = NetworkPacket(0, 'control', json.dumps(self.rt_tbl_D))
        try:
            print('%s: sending routing update from interface %d' % (self, i))
            self.intf_L[i].put(p.to_byte_S(), 'out', False)
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p, i):
        # TODO: add logic to update the routing tables and
        # possibly send out routing updates
        hdr_len = NetworkPacket.dst_S_length + NetworkPacket.prot_S_length
        p = str(p)
        p = json.loads(p[hdr_len:])

        if p == self.rt_tbl_D:
            routes = self.convergeTable(self.convertToList(), [])
            self.listToDict(routes)
            self.formatFtable()
        else:
            self.appendTables(p)

            for x in range(len(self.intf_L)):
                self.send_routes(x)

        print('%s: Received routing update from interface %d' % (self, i))

    ## thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return
