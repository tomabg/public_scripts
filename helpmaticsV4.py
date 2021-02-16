#!/usr/bin/env python
#-*- coding:utf-8 -*-

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
#V3
#create a HM ticket in Helpmatics when an Alarm is open longer Than 20 Minutes
#
#V4
#make new PROCESS Information(BEARBEITUNG) available in Icinga comment
#Remove old comments for closed tickets in Icinga (autoremovetime=float((time.time() - (60 * 60 * 24 * 90))))
#show color for Ticketstatus
#format comment(bold and underline)
#some corrections for host handling
#max number of tickets
#Update Icinga status in HM every 24 h
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
import time
import datetime
import socket

#VARIABLES START:
#Helpmatics wdsl page and HM User
wdsl = 'https://XXXXXXXXXXXXXXXXXXXXXX/portal.nsf/IncidentHandler?wsdl'
HM_username = 'XXXXXXXXXXXXXXXXXXXXXX'
HM_password = 'XXXXXXXXXXXXXXXXXXXXXX'
HM_incident_startswith = 'XOC-'
#HM_incident_startswith = 'ABC-'
autoremovetime=float((time.time() - (60 * 60 * 24 * 90))) #90 days
#autoremovetime=float((time.time() - (60 * 40))) #40 minutes for test/debug
last_state_ok = str(time.time() - (60 * 20)) #only get Icinga objectes longer than 20 minutes NOK
maxnewtickets = 3 #max nember of new tickets per script run..to avoid mass tickets during major outage
numberoftickets = 0
hmstatusupdates = True #should statusupdates send from icinga to HM
hmstatusupdateinterval = datetime.timedelta(hours=24) #how often should HM updated from Icinga
scriptinterval = datetime.timedelta(minutes=12) #how often runs the script + runtime of script e.g. every 10 minutes + maybe 2 minutes runtime
#Icinga API data and API user see /etc/icinga2/conf.d/api-users.conf
icingaserver = 'https://icinga.XXXXXXXXXXXXXXXXXXXXXX:5665'
icingauser = 'root'
icingapassword = 'XXXXXXXXXXXXXXXXXXXXXX'
#VARIABLES END

currenttime = datetime.datetime.now()
scriptintervalseconds = scriptinterval.total_seconds()

history = HistoryPlugin() #for debugging
session = Session()
session.auth = HTTPBasicAuth(HM_username, HM_password)
HMclient = HMClient(wdsl,
    transport=Transport(session=session),
    plugins=[history]) #create Helpmatics client object

Icingaclient = IcingaClient(icingaserver, icingauser, icingapassword) #create icinga client object
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) #workaround as API certificate is self signed in Icinga

#print Icingaclient.objects.get('Host', 'XXXXXXXXXXXXXXXXXXXXXX') #for debugging
#print (client.service.GETINCIDENTDATA('XOC-210121132823-MPu')) #for debugging

#function to convert HM Ticket status
def convert_ticketstatus(statusid):
    translatestatus = {
        '1': "<span style=\"background-color: #FA5858\">offen</span>",
        '2': "<span style=\"background-color: #FFFF00\">in Arbeit</span>",
        '3': "<span style=\"background-color: #0000FF\">extern</span>",
        '4': "<span style=\"background-color: #D358F7\">wartend</span>",
        '5': "<span style=\"background-color: #088A08\">erledigt</span>",
        '6': "<span style=\"background-color: #00FF00\">geschlossen</span>",
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
    if incident_dict['INC']['PROCESS'] is None :
        incident_dict['INC']['PROCESS'] = 'None'
    #print incident_dict
    return incident_dict


#print get_hm_ticket('XOC-210125085233-TPi')

#function to test Incident data from HelpMatics
def test_hm_interface_status(ticketid):
    #hole ticket von HM(XML Format) 
    incident_xml = HMclient.service.GETINCIDENTDATA(ticketid)
    incident_dict = helpers.serialize_object(incident_xml)
    #print incident_dict
    if incident_dict['INC']['ID'] == ticketid :
        #print "Interface Up"
        return True
    else :
        #print "interface Down"
        return False

def convert_last_hard_state(last_hard_state):
    translatestatus = {
        0.0: "OK",
        1.0: "WARNING",
        2.0: "CRITICAL",
        3.0: "UNKNOWN",
    }
    #print translatestatus.get(last_hard_state, "Invalid last_hard_state") #for debugging
    return translatestatus.get(last_hard_state, "Invalid last_hard_state")

def convert_last_hard_state_host(last_hard_state):
    translatestatus = {
        0.0: "UP",
        1.0: "DOWN"
    }
    #print translatestatus.get(last_hard_state, "Invalid last_hard_state") #for debugging
    return translatestatus.get(last_hard_state, "Invalid last_hard_state")



#Icingaclient.objects.get('Host', 'XXXXXXXXXXXXXXXXXXXXXX')

# Icingaclient.actions.add_comment(
#     object_type = 'Host',
#     filters = 'host.name== "XXXXXXXXXXXXXXXXXXXXXX"',
#     author = 'Helpmaticsscript',
#     comment = 'this is a test2')

# Icingaclient.actions.add_comment(
#     object_type = 'Service',
#     filters = 'host.name=="XXXXXXXXXXXXXXXXXXXXXX" && service.name=="icmp"',
#     author = 'Helpmaticsscript',
#     comment = 'this is a service')

# time.sleep(1) # Sleep for 1 seconds because create and immidiate delete leads to "hanging" comments(to fix restart icinga)

# Icingaclient.actions.remove_comment(
#     object_type = 'Host',
#     filters = 'host.name== "XXXXXXXXXXXXXXXXXXXXXX"')

#print get_hm_ticket_status('XOC-210121132823-MPu')
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
            newcomment = comment['attrs']['text'][0:20] + " : was not found in Helpmatics! check TicketID and add new comment\n with correct ticketID e.g.: XOC-210121132823-MPu"
        else :
            newcomment = comment['attrs']['text'][0:20] + " : "  + convert_ticketstatus(HMticket['INC']['STATUS_NO'])  + \
            "\n\n<B><U>SOLUTION:</U></B>\n" + HMticket['INC']['SOLUTION'] + \
            "\n\n<B><U>BEARBEITUNG:</U></B>\n" + HMticket['INC']['PROCESS']
        
        #print repr(newcomment)

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
        #automatic ACK for Alarms with open tickets
        if icingaobject['attrs']['last_hard_state'] != 0.0 and icingaobject['attrs']['acknowledgement'] == 0.0 and int(HMticket['INC']['STATUS_NO']) <= 4:
            # print icingahostname + '!' + icingaservicename
            # print icingaobject['attrs']['last_hard_state']
            # print icingaobject['attrs']['acknowledgement'] 
            # print HMticket['INC']['STATUS_NO']
            if icingaservicename == '' :
                #print "its a host"
                Icingaclient.actions.acknowledge_problem(
                    object_type = 'Host',
                    filters = 'host.name=="'+ icingahostname + '"',
                    author = 'HelpmaticsScript',
                    comment = HMticket['INC']['ID']
                )

            else :
                #print 'its a serverice'
                Icingaclient.actions.acknowledge_problem(
                    object_type = 'Service',
                    filters = 'host.name=="'+ icingahostname +'" && service.name=="'+ icingaservicename +'"',
                    author = 'HelpmaticsScript',
                    comment = HMticket['INC']['ID']
                )
            autoACK = True #setting this to get a "real" comment later and not an ACK comment
            time.sleep(1) #sleep 1 second to avaid inconsistent comments
        #print icingaobject['attrs']['severity']
        #exit (4)

        #create new comment if sth changed or after auto ACK
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
        #removing very old non changed events for closed tickets
        elif comment['attrs']['entry_time'] <=  autoremovetime and int(HMticket['INC']['STATUS_NO']) == 6:
            #print str(comment['attrs']['entry_time']) + '  <= ' + str(autoremovetime) + 'Ticketstatus: ' + str(HMticket['INC']['STATUS_NO'])
            if icingaservicename == '' :
                Icingaclient.actions.remove_comment(
                object_type = 'Host',
                filters = 'host.name== "'+ icingahostname +'"')
            else :
                Icingaclient.actions.remove_comment(
                object_type = 'Service',
                filters = 'host.name=="'+ icingahostname +'" && service.name=="'+ icingaservicename +'"')
           
        #####section Update HM
        if int(HMticket['INC']['STATUS_NO']) <= 4 and hmstatusupdates:
            #print 'check for update HM'
            #convert ticketid to time
            ticketcreationtime = datetime.datetime.fromtimestamp(time.mktime(datetime.datetime.strptime(HMticket['INC']['ID'][0:16] , "XOC-%y%m%d%H%M%S").timetuple()))
            #print icingaobject

            #add updateintervall as long as it is smaller then currenttime..and always check against scriptruntime...if this matches the ticket is updated
            while currenttime > ticketcreationtime :
                ticketcreationtime += hmstatusupdateinterval
                #print abs((ticketcreationtime - currenttime).total_seconds())
                deltaseconds = abs((ticketcreationtime - currenttime).total_seconds())
                #deltaseconds = abs((ticketcreationtime - currenttime).total_seconds)
                #print deltaseconds
                #print scriptintervalseconds
                days_to_find_if_positive = (ticketcreationtime - currenttime).days
                #print days_to_find_if_positive
                if deltaseconds <= scriptintervalseconds and days_to_find_if_positive < 0 :
                    print 'Update HM Ticket'
                    
                    HMTICKETID = str(HMticket['INC']['ID'])
                    if icingaservicename == '' :
                        NEWPROCESSENTRY =  'STATUS: ' + convert_last_hard_state_host( icingaobject['attrs']['last_hard_state'] )+ '             SINCE:  ' + datetime.datetime.fromtimestamp(icingaobject['attrs']['last_state_change']).strftime("%Y-%m-%d %H:%M:%S") +  '\n\n' + \
                        'DETAILS: ' + icingaobject['attrs']['last_check_result']['output'] + '\n\n' + \
                        'This entry was created by ' + __file__ + ' on ' + socket.gethostname()
                    else:
                        NEWPROCESSENTRY =  'STATUS: ' + convert_last_hard_state( icingaobject['attrs']['last_hard_state'] )+ '             SINCE:  ' + datetime.datetime.fromtimestamp(icingaobject['attrs']['last_state_change']).strftime("%Y-%m-%d %H:%M:%S") +  '\n\n' + \
                        'DETAILS: ' + icingaobject['attrs']['last_check_result']['output'] + '\n\n' + \
                        'This entry was created by ' + __file__ + ' on ' + socket.gethostname()
                    print NEWPROCESSENTRY

                    NEWHMTicket_xml = HMclient.service.UPDATEINCIDENT(
                                    ID = HMTICKETID,
                                    USER_ID = 'SVC1Icinga_Sendmail@XXXXXXXXXXXXXXXXXXXXXX.com',
                                    CI_ID = '',
                                    BRIEFDESCRIPTION = '',
                                    REQUEST = '',
                                    PROCESS = NEWPROCESSENTRY, #Bearbeitungsschritte
                                    SOLUTION = '',
                                    MAINCATEGORY = '',
                                    SUBCATEGORY1 = '',
                                    SUBCATEGORY2 = '',
                                    INCIDENT_TYPE = '',
                                    INCIDENT_ROOTCAUSE = '',
                                    STATUS_NO = '', #wartend
                                    REMINDER_HOURS ='',  #Anzahl Stunden
                                    PRIORITY_NO = '', #normal
                                    INCIDENT_OWNER = '',
                                    INCIDENT_EDITOR = '',
                                    SERVICE_CIID = ''
                                )

                    #print NEWHMTicket_xml


##get all NOT OK(longer than 20 Minutes), not in Downtime and NOT ACK objects from Icinga
#print "start getting events"


try :
    hostsNOK = Icingaclient.objects.list(
        object_type = 'Host',
        filters = 'host.last_hard_state !=0 && host.acknowledgement != 1 && host.downtime_depth == 0 && host.last_state_up <=' + last_state_ok
    )
    #print hostsNOK
except :
    hostsNOK = []

try :
    servicessNOK = Icingaclient.objects.list(
        object_type = 'Service',
        filters = 'service.last_hard_state != 0 && service.last_hard_state != 3 && service.downtime_depth == 0 && service.acknowledgement != 1 && service.last_reachable && service.last_state_ok <=' + last_state_ok
    )
except :
    servicessNOK = []


#print hostsNOK
#print servicessNOK
#print len(hostsNOK)
#print len(servicessNOK)
#print servicessNOK


###################GENERATE HOST Ticket

for hostNOK in hostsNOK :
    numberoftickets += 1
    if  numberoftickets > maxnewtickets :
        exit(4)

    #print hostNOK['attrs']['last_hard_state']
    BRIEFDESCRIPTION = 'ICINGA: ' + hostNOK['type'] + ' ' + hostNOK['attrs']['__name'] + ' is ' + convert_last_hard_state_host( hostNOK['attrs']['last_hard_state'] )  + '!'
    #print BRIEFDESCRIPTION
    #print serviceNOK['attrs']['last_check_result']['check_source']
    REQUEST = '***** Host Monitoring on ' + hostNOK['attrs']['last_check_result']['check_source'] + ' *****\n\n' + \
    hostNOK['attrs']['__name'] + ' is ' + convert_last_hard_state_host( hostNOK['attrs']['last_hard_state'] )  + '!\n\n' + \
    'INFO : ' + hostNOK['attrs']['last_check_result']['output'] + '\n\n' + \
    'When : ' + datetime.datetime.fromtimestamp(hostNOK['attrs']['last_state_change']).strftime("%Y-%m-%d %H:%M:%S") + '\n' + \
    'Host : ' +  hostNOK['attrs']['name'] + '\n\n\n\n' + \
    'This Ticket was created by ' + __file__ + ' on ' + socket.gethostname()
    #print REQUEST
    #print hostNOK['attrs']['name']

    try :
        NEWHMTicket_xml = HMclient.service.CREATEINCIDENT(
                USER_ID = 'SVC1Icinga_Sendmail@XXXXXXXXXXXXXXXXXXXXXX.com',
                CI_ID = '',
                BRIEFDESCRIPTION = BRIEFDESCRIPTION,
                REQUEST = REQUEST,
                PROCESS = '', #Bearbeitungsschritte
                SOLUTION = '',
                MAINCATEGORY = 'Monitoring',
                SUBCATEGORY1 = 'Icinga',
                SUBCATEGORY2 = 'Server-Kapazität',
                INCIDENT_TYPE = 'Incident',
                INCIDENT_ROOTCAUSE = 'Fehler',
                STATUS_NO = '4', #wartend
                REMINDER_HOURS ='72',  #Anzahl Stunden
                PRIORITY_NO = '2', #normal
                INCIDENT_OWNER = '[Operations Team XOC]',
                INCIDENT_EDITOR = '[Operations Team XOC]',
                SERVICE_CIID = '',
                SENDINFOMAILTOUSER = '0' #1 means send mail to user/group
            )
        #getting back new HM Ticket to ACK problem and add Ticket as comment
        NEWHMTicket_dict = helpers.serialize_object(NEWHMTicket_xml)
        #print NEWHMTicket_dict['INC']['ID']
    except :
        NEWHMTicket_dict = []
    if   NEWHMTicket_dict != [] :
        try : 
            Icingaclient.actions.acknowledge_problem(
                object_type = 'Host',
                filters = 'host.name=="'+ hostNOK['attrs']['name'] +'"',
                author = 'HelpmaticsScript',
                comment = NEWHMTicket_dict['INC']['ID'],
                persistent = True
            )
        except :
            print 'could not ACK host'


NEWHMTicket_dict = []

###################GENERATE SERVICE Ticket
for serviceNOK in servicessNOK :
    numberoftickets += 1
    if  numberoftickets > maxnewtickets :
        exit(4)
    
    #print serviceNOK['attrs']['last_hard_state']
    #print serviceNOK['type'] + ' ' + serviceNOK['attrs']['__name'] + ' is ' + convert_last_hard_state( serviceNOK['attrs']['last_hard_state'] )  + '!'
    BRIEFDESCRIPTION = 'ICINGA: ' + serviceNOK['type'] + ' ' + serviceNOK['attrs']['__name'] + ' is ' + convert_last_hard_state( serviceNOK['attrs']['last_hard_state'] )  + '!'
    #print BRIEFDESCRIPTION
    #print serviceNOK['attrs']['last_check_result']['check_source']
    REQUEST = '***** Service Monitoring on ' + serviceNOK['attrs']['last_check_result']['check_source'] + ' *****\n\n' + \
    serviceNOK['attrs']['__name'] + ' is ' + convert_last_hard_state( serviceNOK['attrs']['last_hard_state'] )  + '!\n\n' + \
    'INFO : ' + serviceNOK['attrs']['last_check_result']['output'] + '\n\n' + \
    'When : ' + datetime.datetime.fromtimestamp(serviceNOK['attrs']['last_state_change']).strftime("%Y-%m-%d %H:%M:%S") + '\n' + \
    'Service : ' + serviceNOK['attrs']['display_name'] + '\n' + \
    'Host : ' +  serviceNOK['attrs']['host_name']  + '\n\n\n\n' + \
    'This Ticket was created by ' + __file__ + ' on ' + socket.gethostname()
    #print REQUEST
    #print serviceNOK['attrs']['name']

    try :
        NEWHMTicket_xml = HMclient.service.CREATEINCIDENT(
                USER_ID = 'SVC1Icinga_Sendmail@XXXXXXXXXXXXXXXXXXXXXX.com',
                CI_ID = '',
                BRIEFDESCRIPTION = BRIEFDESCRIPTION,
                REQUEST = REQUEST,
                PROCESS = '', #Bearbeitungsschritte
                SOLUTION = '',
                MAINCATEGORY = 'Monitoring',
                SUBCATEGORY1 = 'Icinga',
                SUBCATEGORY2 = 'Server-Kapazität',
                INCIDENT_TYPE = 'Incident',
                INCIDENT_ROOTCAUSE = 'Fehler',
                STATUS_NO = '4', #wartend
                REMINDER_HOURS ='72',  #Anzahl Stunden
                PRIORITY_NO = '2', #normal
                INCIDENT_OWNER = '[Operations Team XOC]',
                INCIDENT_EDITOR = '[Operations Team XOC]',
                SERVICE_CIID = '',
                SENDINFOMAILTOUSER = '0' #1 means send mail to user/group
            )
        #getting back new HM Ticket to ACK problem and add Ticket as comment
        NEWHMTicket_dict = helpers.serialize_object(NEWHMTicket_xml)
        #print NEWHMTicket_dict['INC']['ID']
    except :
        NEWHMTicket_dict = []
    if   NEWHMTicket_dict != [] :
        try : 
            Icingaclient.actions.acknowledge_problem(
                object_type = 'Service',
                filters = 'host.name=="'+ serviceNOK['attrs']['host_name'] +'" && service.name=="'+ serviceNOK['attrs']['name'] +'"',
                author = 'HelpmaticsScript',
                comment = NEWHMTicket_dict['INC']['ID'],
                persistent = True
            )
        except :
            print 'could not ACK service'




#print Icingaclient.objects.list('Host', filters='match("XXXXXXXXXXXXXXXXXXXXXX", host.name)')

##### This can DEBUG commands can Help to find Out what was sended to Helpmatics(is initialzed in Helpmatics Client object) #############
#print('#############  SEND  ##################')
#print(etree.tostring(history.last_sent["envelope"], encoding="unicode", pretty_print=True))
#print('#############  RECEIVED  ##################')
#print(etree.tostring(history.last_received["envelope"], encoding="unicode", pretty_print=True))
