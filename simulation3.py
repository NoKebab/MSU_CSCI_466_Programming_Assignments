"""
Created on Oct 12, 2016

@author: mwittie
"""

import link3
import threading
from time import sleep

import network3
from rprint import print

# configuration parameters
router_queue_size = 0  # 0 means unlimited
simulation_time = 15  # give the network sufficient time to transfer all packets before quitting

if __name__ == '__main__':
    object_L = []  # keeps track of objects, so we can kill their threads

    # create network nodes configured to reflect network.png topology
    client1 = network3.Host(1)  # host 1
    object_L.append(client1)
    client2 = network3.Host(2)  # host 2
    object_L.append(client2)

    server1 = network3.Host(3)  # host 3
    object_L.append(server1)
    server2 = network3.Host(4)  # host 4
    object_L.append(server2)

    # table_name -> {destination -> interface}
    routing_tables = {'A': {3: 0, 4: 1},
                      'B': {3: 0, 4: 0},
                      'C': {3: 0, 4: 0},
                      'D': {3: 0, 4: 1}}
    # name, intf_count, max_queue_size, routing_table
    router_a = network3.Router('A', 2, router_queue_size, routing_tables.get('A'))
    object_L.append(router_a)
    router_b = network3.Router('B', 1, router_queue_size, routing_tables.get('B'))
    object_L.append(router_b)
    router_c = network3.Router('C', 1, router_queue_size, routing_tables.get('C'))
    object_L.append(router_c)
    router_d = network3.Router('D', 2, router_queue_size, routing_tables.get('D'))
    object_L.append(router_d)

    # create a Link Layer to keep track of links between network nodes
    link_layer = link3.LinkLayer()
    object_L.append(link_layer)

    # add all the links
    # link parameters: from_node, from_intf_num, to_node, to_intf_num, mtu
    link_layer.add_link(link3.Link(client1, 0, router_a, 0, 50))
    link_layer.add_link(link3.Link(client2, 0, router_a, 0, 50))

    link_layer.add_link(link3.Link(router_a, 0, router_b, 0, 50))
    link_layer.add_link(link3.Link(router_a, 1, router_c, 0, 50))

    link_layer.add_link(link3.Link(router_b, 0, router_d, 0, 30))

    link_layer.add_link(link3.Link(router_c, 0, router_d, 0, 50))

    link_layer.add_link(link3.Link(router_d, 0, server1, 0, 50))
    link_layer.add_link(link3.Link(router_d, 1, server2, 0, 50))

    # start all the objects
    thread_L = [threading.Thread(name=object.__str__(), target=object.run) for object in object_L]
    for t in thread_L:
        t.start()

    # create some send events
    # msg0 = "Let's see Paul Allen's card."  # short message that does not need segmentation across any interface
    # longer messages that need to be segmented and then reassembled at the most
    msg1 = 'Look at that subtle off-white coloring. The tasteful thickness of it. Oh, my God. It even has a watermark.'
    msg2 = 'Do you like Huey Lewis and the News? Their early work was a little too new wave for my tastes.'
    for i in range(1):
        # included source address
        client1.udt_send(3, msg1, i)
        # client1.udt_send(3, msg0, i + 1)
        client2.udt_send(4, msg2, i)
        # client2.udt_send(4, msg0, i + 1)

    # give the network sufficient time to transfer all packets before quitting
    sleep(simulation_time)

    # join all threads
    for o in object_L:
        o.stop = True
    for t in thread_L:
        t.join()

    print("All simulation threads joined")
