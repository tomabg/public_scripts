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
wdsl = 'https://[HM-Server]/[subURL]/portal.nsf/IncidentHandler?wsdl'
HM_username = 'exampleUser'
HM_password = 'examplePW'
HM_incident_startswith = 'XYZ-'
#Icinga API data and API user see /etc/icinga2/conf.d/api-users.conf
icingaserver = 'https://examplehost.com:5665'
icingauser = 'root'
icingapassword = 'examplePW'
#VARIABLES END

history = HistoryPlugin() #for debugging
session = Session()
session.auth = HTTPBasicAuth(HM_username, HM_password)
HMclient = HMClient(wdsl,
    transport=Transport(session=session),
    plugins=[history]) #create Helpmatics client object

Icingaclient = IcingaClient(icingaserver, icingauser, icingapassword) #create icinga client object
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) #workaround as API certificate is self signed in Icinga

#print Icingaclient.objects.get('Host', 'SDCAWG014') #for debugging
#print (client.service.GETINCIDENTDATA('XOC-210121132823-MPu')) #for debugging

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
def get_hm_ticket_status(ticketid):
    #hole ticket von HM(XML Format) 
    incident_xml = HMclient.service.GETINCIDENTDATA(ticketid)
    #convertiere XML in ein ordereddict um es gezielt auszuwerten
    incident_dict = helpers.serialize_object(incident_xml)
    #print incident_dict #for debugging
    #mache Status Lesbarer
    #print convert_ticketstatus(incident_dict['INC']['STATUS_NO']) #for debugging
    #print incident_dict['INC']['SOLUTION']
    if incident_dict['INC']['ID'] is None:
        return " : was not found in Helpmatics! check TicketID and add new comment\n with correct ticketID e.g.: XOC-210121132823-MPu"
    if incident_dict['INC']['SOLUTION'] is None :
        incident_dict['INC']['SOLUTION'] = 'None'
    return convert_ticketstatus(incident_dict['INC']['STATUS_NO']) + "\n\n SOLUTION:\n" + incident_dict['INC']['SOLUTION']


#Icingaclient.objects.get('Host', 'SDCAWG014')

# Icingaclient.actions.add_comment(
#     object_type = 'Host',
#     filters = 'host.name== "EXAMPLEHOST"',
#     author = 'Helpmaticsscript',
#     comment = 'this is a test2')

# Icingaclient.actions.add_comment(
#     object_type = 'Service',
#     filters = 'host.name=="EXAMPLEHOST" && service.name=="icmp"',
#     author = 'Helpmaticsscript',
#     comment = 'this is a service')

# time.sleep(1) # Sleep for 1 seconds because create and immidiate delete leads to "hanging" comments(to fix restart icinga)

# Icingaclient.actions.remove_comment(
#     object_type = 'Host',
#     filters = 'host.name== "EXAMPLEHOST"')

#print get_hm_ticket_status('XYZ-210121132823-MMu')
#print len(Icingaclient.objects.list('Comment')) #for debugging

#get all comments from Icinga
Commentlist = Icingaclient.objects.list('Comment')

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
        newcomment = comment['attrs']['text'][0:20] + " : "  + get_hm_ticket_status(comment['attrs']['text'][0:20])
        #print newcomment
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


#print Icingaclient.objects.list('Host', filters='match("EXAMPLEHOST", host.name)')

##### This can DEBUG commands can Help to find Out what was sended to Helpmatics(is initialzed in Helpmatics Client object) #############
#print('#############  SEND  ##################')
#print(etree.tostring(history.last_sent["envelope"], encoding="unicode", pretty_print=True))
#print('#############  RECEIVED  ##################')
#print(etree.tostring(history.last_received["envelope"], encoding="unicode", pretty_print=True))

