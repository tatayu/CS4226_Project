'''
Please add your name: Yu Xiaoxue
Please add your matric number: A0187744N
'''

import sys
import os
#from sets import Set

from pox.core import core

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_forest

from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr

import time

log = core.getLogger()

TTL = 30
idle_TTL = 30
hard_TTL = 30

PREMIUM = 1
NORMAL = 0

PREMIUM_PRIORITY = 100
FIREWALL_PRIORITY = 200

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        self.table = {}
        self.table_ttl = {}
        #self.policies = [] #src, dst, port
        self.premium = []
        

    def _handle_PacketIn (self, event):
        packet = event.parsed
        dpid = event.dpid
        src = packet.src
        dst = packet.dst
        inport = event.port
        
        ip_src = None
        ip_dst = None
        
        #check packet type and get IP address
        if(packet.type == packet.IP_TYPE):
            ip_src = packet.payload.srcip
            ip_dst = packet.payload.dstip       
        elif(packet.type == packet.ARP_TYPE):
            ip_src = packet.payload.protosrc
            ip_dst = packet.payload.protodst

    	# install entries to the route table
        def install_enqueue(event, packet, outport, q_id):    
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, inport)
            msg.priority = PREMIUM_PRIORITY
            msg.actions.append(of.ofp_action_enqueue(port = outport, queue_id = q_id))
            msg.data = event.ofp
            msg.idle_timeout = idle_TTL
            msg.hard_timeout = hard_TTL
            event.connection.send(msg)
            return

    	# Check the packet and decide how to route the packet
        def forward(message = None):
            
            #both src and dst are premium
            if(ip_src in self.premium and ip_dst in self.premium):
                q_id = PREMIUM 
            else:
                q_id = NORMAL

            #if timeout, pop from ttl table
            if dpid in self.table:
                if dst in self.table_ttl[dpid]:
                    if time.time() - self.table_ttl[dpid][dst] > 30.0:
                        self.table[dpid].pop(dst)
                        self.table_ttl[dpid].pop(dst)
            
            #create table for unknow dst
            if dpid not in self.table:
                self.table[dpid] = {}
                self.table_ttl[dpid] = {}
            
            if dst not in self.table[dpid]:
                self.table[dpid][src] = inport
                self.table_ttl[dpid][src] = time.time()
                flood()
 
            else:
                outport = self.table[dpid][dst] #get outport for known dst
                install_enqueue(event, packet, outport, q_id)

            
                

        # When it knows nothing about the destination, flood but don't install the rule
        def flood (message = None):
            # define your message here
            
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.in_port = inport
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            event.connection.send(msg)
            return

        forward()


    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        
        def readPolicy():
            policies = []
            #premium = []
            
            #read policies
            f = open("policy.in", "r")
            first_line = f.readline().split(" ")
            num_fw = first_line[0]
            num_pre = first_line[1]
            
            #store firewall policies
            for rule in range(int(num_fw)):
                l = f.readline().strip().split(",")
                if len(l) == 2:
                    policies.append((None, l[0], l[1]))
                elif len(l) == 3:
                    policies.append((l[0], l[1], l[2]))

            #store premium policies
            for host in range(int(num_pre)):
                a = f.readline()
                self.premium.append(a)

            return policies


        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            # define your message here
            from_host, to_host, outport = policy
            print(from_host, to_host, outport)
            msg = of.ofp_flow_mod()
            msg.priority = FIREWALL_PRIORITY
            #msg.actions.append(of.ofp_action_output(port = of.OFPP_NONE))
            #if block by firewall, drop message
            msg.match.dl_type = 0x800
            msg.match.nw_proto = 6
            
            #only block to host
            if from_host is not None:
                msg.match.nw_src = IPAddr(from_host)
 
            msg.match.nw_dst = IPAddr(to_host)
            msg.match.tp_dst = int(outport)
                
            connection.send(msg)

        policies = readPolicy()
        for policy in policies:
            sendFirewallPolicy(event.connection, policy)
            

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_forest.launch()

    # Starting the controller module
    core.registerNew(Controller)
