#Author: Thomas Pietzka COC AG
#
#script to check local fedora version and send a Desktop Notificatin to all logged in users if version is lower
#
#example to send a notification to user tester with UID 1001
#sudo sudo DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus  -u tester notify-send -u normal -i software-update-urgent "Fedora Upgrade Available" "An new Version of Fedora is available."
#
#script can be setup as a cron job for example(or deployed with rpm):
#copy to /etc/cron.daliy/fedora32_upgrade_notify_user.sh
#chmod +x /etc/cron.daliy/fedora32_upgrade_notify_user.sh

source /etc/os-release

#Fedora Target version..modify to the needs
TARGETVERSIONID=32

if [ $TARGETVERSIONID -gt $VERSION_ID ]
then
	URGENCY="normal"
	ICON="software-update-urgent"
	MESSAGESUMMARY="Fedora Upgrade Available"
	MESSAGEBODY="An new Version of Fedora is available.\n\
	Execute following script to perform the Upgrade:\n\
	sudo  /usr/local/bin/upgrade_fedora32.sh"
	
	for USERID in `ls /run/user/`
	do
		USERNAME=`getent passwd $USERID | cut -d: -f1`
		sudo sudo DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$USERID/bus  -u $USERNAME notify-send -u $URGENCY -i $ICON "${MESSAGESUMMARY}" "${MESSAGEBODY}"
	done

else
	#delete scriptfile from /etc/cron.daliy/fedora32_upgrade_notify_user.sh
	rm $0
fi
