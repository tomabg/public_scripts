#!/usr/bin/env python

#Author: Thomas Pietzka COC AG
#Purpose:
#This script should get TicketID from Icinga comment and provide Ticket Status and Solution in
#a new comment in Icinga.
#This script will check if comment in Icinga starts with "XOC-" what is indicating a Ticket.
#Then Ticketdata is fetched from Helpmatics and comment in Icinga is Updated with Ticketstatus and Solution.
#
#Requirements/Modules:
#pip is needed as this modules are not rpm packaged for CentOS
#on CentOS:
#yum install python-pip
#SOAP Client used: https://github.com/mvantellingen/python-zeep
#on Windows:
#python -m pip install --upgrade pip
#python -m  pip install zeep==3.4.0
#on CentOS:
#pip install zeep==3.4.0
#https://github.com/joni1993/icinga2apic
#on Windows:
# python -m pip install icinga2apic
#on CentOS:
#pip install icinga2apic
#
#Usage:
#Copy script to any location and make it executable
#chmod +x /etc/icinga2/scripts/icinga_helpmatics/helpmatics.py
#Update Variable part
#execute the script as a Test
#for troubleshooting and testing purpose you can uncomment prints
#finally add cron-Job for example every 10 Minutes
#crontab -e
#*/10 * * * * /etc/icinga2/scripts/icinga_helpmatics/helpmatics.py>> ~/helpmatics_cron.log 2>&1
#
#Versions:
#V2
#Test HM SOAP Interface to make shure it is available and delivers correct content(if not exitcode 3)
#ACK open alarms when an assigned Ticket is not closed or done to avoid unneeded notifications
#INFO how this works: script is scheduled every 10 min and notification is send after 20 minutes
#
#

from zeep import helpers
from zeep import Client as HMClient
from zeep.transports import Transport
from zeep.plugins import HistoryPlugin
from requests import Session
from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from icinga2apic.client import Client as IcingaClient
import urllib3
from lxml import etree #for debugging
import time #for debugging

#VARIABLES START:
#Helpmatics wdsl page and HM User
wdsl = 'https://XXXXXX/portal.nsf/IncidentHandler?wsdl'
HM_username = 'XXXXXX'
HM_password = 'XXXXX'
HM_incident_startswith = 'XOC-'
#Icinga API data and API user see /etc/icinga2/conf.d/api-users.conf
icingaserver = 'https://XXXXX:5665'
icingauser = 'root'
icingapassword = 'XXXXX'
#VARIABLES END

history = HistoryPlugin() #for debugging
session = Session()
session.auth = HTTPBasicAuth(HM_username, HM_password)
HMclient = HMClient(wdsl,
    transport=Transport(session=session),
    plugins=[history]) #create Helpmatics client object

Icingaclient = IcingaClient(icingaserver, icingauser, icingapassword) #create icinga client object
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) #workaround as API certificate is self signed in Icinga

#print Icingaclient.objects.get('Host', 'XXXXX') #for debugging
#print (client.service.GETINCIDENTDATA('XXXXXX')) #for debugging

#function to convert HM Ticket status
def convert_ticketstatus(statusid):
    translatestatus = {
        '1': "offen",
        '2': "in Arbeit",
        '3': "extern",
        '4': "wartend",
        '5': "erledigt",
        '6': "geschlossen",
    }
    #print translatestatus.get(statusid, "Invalid Ticketstatus") #for debugging
    return translatestatus.get(statusid, "Invalid Ticketstatus")

#function to get Incident data from HelpMatics
def get_hm_ticket(ticketid):
    #hole ticket von HM(XML Format) 
    incident_xml = HMclient.service.GETINCIDENTDATA(ticketid)
    #convertiere XML in ein ordereddict um es gezielt auszuwerten
    incident_dict = helpers.serialize_object(incident_xml)
    #print incident_dict #for debugging
    #mache Status Lesbarer
    #print convert_ticketstatus(incident_dict['INC']['STATUS_NO']) #for debugging
    #print incident_dict['INC']['SOLUTION']
    if incident_dict['INC']['SOLUTION'] is None :
        incident_dict['INC']['SOLUTION'] = 'None'
    return incident_dict

#function to test Incident data from HelpMatics
def test_hm_interface_status(ticketid):
    #hole ticket von HM(XML Format) 
    incident_xml = HMclient.service.GETINCIDENTDATA(ticketid)
    incident_dict = helpers.serialize_object(incident_xml)
    if incident_dict['INC']['ID'] == ticketid :
        #print "Interface Up"
        return True
    else :
        #print "interface Down"
        return False



#Icingaclient.objects.get('Host', 'SDCAWG014')

# Icingaclient.actions.add_comment(
#     object_type = 'Host',
#     filters = 'host.name== "XXXXXX"',
#     author = 'Helpmaticsscript',
#     comment = 'this is a test2')

# Icingaclient.actions.add_comment(
#     object_type = 'Service',
#     filters = 'host.name=="XXXXX" && service.name=="icmp"',
#     author = 'Helpmaticsscript',
#     comment = 'this is a service')

# time.sleep(1) # Sleep for 1 seconds because create and immidiate delete leads to "hanging" comments(to fix restart icinga)

# Icingaclient.actions.remove_comment(
#     object_type = 'Host',
#     filters = 'host.name== "XXXXXXX"')

#print get_hm_ticket_status('XXXXXXX')
#print len(Icingaclient.objects.list('Comment')) #for debugging

#get all comments from Icinga
Commentlist = Icingaclient.objects.list('Comment')
invalid_hm_response_counter = 0

#check HM interface ..after 5 times failed exit script
for comment in Commentlist:
    if comment['attrs']['text'].startswith(HM_incident_startswith):
        if test_hm_interface_status(comment['attrs']['text'][0:20]) is True :
            break
        else :
            invalid_hm_response_counter += 1
            #end script after 5 times failed to get correct HM response
            if invalid_hm_response_counter == 5:
                exit(3)


#iterate over all comments..check if it could be a ticketID..and finally fill Helpmatics-data in a new comment
for comment in Commentlist:
    #print comment['attrs']['text'] , comment['attrs']['host_name'],  comment['attrs']['service_name']
    if comment['attrs']['text'].startswith(HM_incident_startswith):
        #print comment['attrs']['text'][0:20] #for debugging
        #print get_hm_ticket_status(comment['attrs']['text'][0:20])
        icingahostname = comment['attrs']['host_name']
        icingaservicename = comment['attrs']['service_name']
        #print icingahostname
        #print icingaservicename
        HMticket = get_hm_ticket(comment['attrs']['text'][0:20])
        #print HMticket
        #print comment['attrs']['text'][0:20] + " : "  + convert_ticketstatus(HMticket['INC']['STATUS_NO'])  + "\n\n SOLUTION:\n" + HMticket['INC']['SOLUTION']
        if HMticket['INC']['ID'] is None:
            newcomment = comment['attrs']['text'][0:20] + " : was not found in Helpmatics! check TicketID and add new comment\n with correct ticketID e.g.: XXXXXXX"
        else :
            newcomment = comment['attrs']['text'][0:20] + " : "  + convert_ticketstatus(HMticket['INC']['STATUS_NO'])  + "\n\n SOLUTION:\n" + HMticket['INC']['SOLUTION']
        #print newcomment
        #print HMticket['INC']['ID']
        ###checking status of the service/host for automatic ACK
        if icingaservicename == '' :
            icingaobject = Icingaclient.objects.get(
                object_type = 'Host',
                name = icingahostname
            )
        else :
            icingaobject = Icingaclient.objects.get(
                object_type = 'Service',
                name = icingahostname + '!' + icingaservicename
            )

        #print icingahostname + '!' + icingaservicename
        #print icingaobject['attrs']['last_hard_state']
        #print icingaobject['attrs']['acknowledgement'] 
        autoACK = False #new variable should indicate if Alarm was ACKed

        if icingaobject['attrs']['last_hard_state'] != 0.0 and icingaobject['attrs']['acknowledgement'] == 0.0 and int(HMticket['INC']['STATUS_NO']) <= 4:
            # print icingahostname + '!' + icingaservicename
            # print icingaobject['attrs']['last_hard_state']
            # print icingaobject['attrs']['acknowledgement'] 
            # print HMticket['INC']['STATUS_NO']
            if icingaservicename == '' :
                print "its a host"
                Icingaclient.actions.acknowledge_problem(
                    object_type = 'Host',
                    filters = 'host.name=="'+ icingahostname,
                    author = 'HelpmaticsScript',
                    comment = HMticket['INC']['ID']
                )

            else :
                print 'its a serverice'
                Icingaclient.actions.acknowledge_problem(
                    object_type = 'Service',
                    filters = 'host.name=="'+ icingahostname +'" && service.name=="'+ icingaservicename +'"',
                    author = 'HelpmaticsScript',
                    comment = HMticket['INC']['ID']
                )
            autoACK = True #as the module not allow persistent comment wee need to rewrite it below issue opened https://github.com/joni1993/icinga2apic/issues/3
            time.sleep(1) #sleep 1 second to avaid inconsistent comments
        #print icingaobject['attrs']['severity']
        #exit (4)

        if newcomment != comment['attrs']['text'] or autoACK is True:
            #print newcomment
            #print comment['attrs']['text']
            #wenn service leer ist es ein hostcomment
            if icingaservicename == '' :
                Icingaclient.actions.remove_comment(
                    object_type = 'Host',
                    filters = 'host.name== "'+ icingahostname +'"')
                Icingaclient.actions.add_comment(
                    object_type = 'Host',
                    filters = 'host.name== "'+ icingahostname +'"',
                    author = 'HelpmaticsScript',
                    comment = newcomment)
            #ansonsten ist es ein servicecomment
            else :
                Icingaclient.actions.remove_comment(
                    object_type = 'Service',
                    filters = 'host.name=="'+ icingahostname +'" && service.name=="'+ icingaservicename +'"')

                Icingaclient.actions.add_comment(
                    object_type = 'Service',
                    filters = 'host.name=="'+ icingahostname +'" && service.name=="'+ icingaservicename +'"',
                    author = 'HelpmaticsScript',
                    comment = newcomment)




#print Icingaclient.objects.list('Host', filters='match("XXXXXX", host.name)')

##### This can DEBUG commands can Help to find Out what was sended to Helpmatics(is initialzed in Helpmatics Client object) #############
#print('#############  SEND  ##################')
#print(etree.tostring(history.last_sent["envelope"], encoding="unicode", pretty_print=True))
#print('#############  RECEIVED  ##################')
#print(etree.tostring(history.last_received["envelope"], encoding="unicode", pretty_print=True))
