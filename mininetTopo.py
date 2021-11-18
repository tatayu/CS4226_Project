'''
Please add your name: Yu Xiaoxue
Please add your matric number: A0187744N
'''

import os
import sys
import atexit
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import Link
from mininet.link import TCLink
from mininet.node import RemoteController

net = None

class TreeTopo(Topo):
			
    def __init__(self):
		# Initialize topology
        Topo.__init__(self)  
        self.linkInfo = {}      
	
        f = open("topology.in", "r")

        #get the number of host, switch and link
        lines = f.readline()
        num = lines.split(" ")
        N = num[0] #host
        M = num[1] #switch
        L = num[2] #link

        #print(N, M, L)

        for host in range (int(N)):
            self.addHost('h%s' % (host + 1)) #add host
        
        for switch in range (int(M)):
            sconfig = {'dpid': "%016x" % (switch + 1) }
            self.addSwitch('s%s' % (switch+ 1), **sconfig) #add switch

        for link in range (int(L)):   
            l = f.readline()
            c = l.split(",")
            self.addLink(c[0], c[1]) #add link
            
            #add to bankwidth linkInfo, bi-direction 
            if c[0] not in self.linkInfo:
                self.linkInfo[c[0]] = {}
            
            if c[1] not in self.linkInfo:
                self.linkInfo[c[1]] = {}
            
            self.linkInfo[c[0]][c[1]] = int(c[2])
            self.linkInfo[c[1]][c[0]] = int(c[2])
        
        #print self.links(True, False, True) 

def create(interface, bw):
    bw = 1000000 * bw #change Mbps to bps
    normal = 0.5 * bw 
    premium = 0.8 * bw

    #create queue
    os.system('sudo ovs-vsctl -- set Port %s qos=@newqos \
                -- --id=@newqos create QoS type=linux-htb other-config:max-rate=%d queues=0=@q0,1=@q1\
                -- --id=@q0 create queue other-config:max-rate=%d \
                -- --id=@q1 create queue other-config:min-rate=%d'
                %(interface, bw, int(normal), int(premium)))


def startNetwork():
    info('** Creating the tree network\n')
    topo = TreeTopo()

    global net
    net = Mininet(topo=topo, link = Link,
                  controller=lambda name: RemoteController(name, ip='192.168.56.104'),
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()
    

    # Create QoS Queues
    for switch in net.switches: #check all the switches
        for intf in switch.intfList(): #interface sorted by port num
            if intf.link:
                node1 = intf.link.intf1.node
                node2 = intf.link.intf2.node
                if(node1 == switch):
                    dest = node2
                    interface = intf.link.intf1 #get interface
                else:
                    dest = node1
                    interface = intf.link.intf2
                
                bandwidth = topo.linkInfo[switch.name][dest.name] #get the bandwidth of the link
                interface_name = interface.name
                create(interface_name, bandwidth)
    
    info('** Running CLI\n')
    CLI(net)

def stopNetwork():
    if net is not None:
        net.stop()
        # Remove QoS and Queues
        os.system('sudo ovs-vsctl --all destroy Qos')
        os.system('sudo ovs-vsctl --all destroy Queue')


if __name__ == '__main__':
    # Force cleanup on exit by registering a cleanup function
    atexit.register(stopNetwork)

    # Tell mininet to print useful information
    setLogLevel('info')
    startNetwork()
