import network_Final
import link1
import threading
from time import sleep
from rprint import print

##configuration parameters
router_queue_size = 0  # 0 means unlimited
simulation_time = 15  # give the network_Final sufficient time to execute transfers

if __name__ == '__main__':
    object_L = []  # keeps track of objects, so we can kill their threads at the end

    # create network_Final hosts
    host_1 = network_Final.Host('H1')
    object_L.append(host_1)
    host_2 = network_Final.Host('H2')
    object_L.append(host_2)

    # create routers and cost tables for reaching neighbors
    cost_D = {'H1': {0: 1}, 'RB': {1: 2}, 'RC': {2: 3}}  # {neighbor: {interface: cost}}
    router_a = network_Final.Router(name='RA',
                                    cost_D=cost_D,
                                    max_queue_size=router_queue_size)
    object_L.append(router_a)

    cost_D = {'RA': {0: 2}, 'RD': {1: 1}}  # {neighbor: {interface: cost}}
    router_b = network_Final.Router(name='RB',
                                    cost_D=cost_D,
                                    max_queue_size=router_queue_size)
    object_L.append(router_b)

    cost_D = {'RA': {0: 3}, 'RD': {1: 2}}  # {neighbor: {interface: cost}}
    router_c = network_Final.Router(name='RC',
                                    cost_D=cost_D,
                                    max_queue_size=router_queue_size)
    object_L.append(router_c)

    cost_D = {'RB': {0: 1}, 'RC': {1: 2}, 'H2': {2: 1}}  # {neighbor: {interface: cost}}
    router_d = network_Final.Router(name='RD',
                                    cost_D=cost_D,
                                    max_queue_size=router_queue_size)
    object_L.append(router_d)

    # create a Link Layer to keep track of link1s between network_Final nodes
    link1_layer = link1.LinkLayer()
    object_L.append(link1_layer)

    # add all the link1s - need to reflect the connectivity in cost_D tables above
    link1_layer.add_link(link1.Link(host_1, 0, router_a, 0))
    link1_layer.add_link(link1.Link(router_a, 1, router_b, 0))
    link1_layer.add_link(link1.Link(router_a, 2, router_c, 0))
    link1_layer.add_link(link1.Link(router_b, 1, router_d, 0))
    link1_layer.add_link(link1.Link(router_d, 1, router_c, 1))
    link1_layer.add_link(link1.Link(router_d, 2, host_2, 0))

    # start all the objects
    thread_L = []
    for obj in object_L:
        thread_L.append(threading.Thread(name=obj.__str__(), target=obj.run))

    for t in thread_L:
        t.start()

    ## compute routing tables
    router_a.send_routes(1)  # one update starts the routing process
    sleep(simulation_time)  # let the tables converge
    print("Converged routing tables")
    for obj in object_L:
        if str(type(obj)) == "<class 'network_Final.Router'>":
            obj.print_routes()

    # send packet from host 1 to host 2
    host_1.udt_send('H2', 'MESSAGE_FROM_H1')
    sleep(simulation_time)
    host_2.udt_send('H1', 'MESSAGE_FROM_H2')
    sleep(simulation_time)

    # join all threads
    for o in object_L:
        o.stop = True
    for t in thread_L:
        t.join()

    print("All simulation threads joined")
