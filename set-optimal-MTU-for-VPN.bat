@echo off
rem This batch will find out maximum MTU between local and remote host.

SetLocal EnableDelayedExpansion
set MTU=1473
set LASTGOOD=0
set LASTBAD=65536
set PACKETSIZE=28
set SERVER=217.5.128.254




rem Check server reachability.
ping -n 2 -l 0 -f -4 !SERVER! 1>nul
if !ERRORLEVEL! NEQ 0 (
  echo Error: cannot ping !SERVER!. Run "ping -n 1 -l 0 -f -4 !SERVER!" to see details.
  goto :error
)



:seek
rem Start looking for the maximum MTU.
ping -n 2 -l !MTU! -f -4 !SERVER! 1>nul
if !ERRORLEVEL! EQU 0 (
  set /A LASTGOOD=!MTU!
  set /A "MTU=(!MTU! + !LASTBAD!) / 2"
  echo Test PING with MTU Size: !MTU!
  if !MTU! NEQ !LASTGOOD! goto :seek
) else (
  set /A LASTBAD=!MTU!  
  set /A "MTU=(!MTU! + !LASTGOOD!) / 2"
  if !MTU! NEQ !LASTBAD! goto :seek
)

rem for /f "tokens=2 delims==" %%F in ('wmic nic where "NetConnectionStatus=2 and AdapterTypeId=0 and PhysicalAdapter=TRUE and  NOT Name LIKE '%%VPN%%'" get  NetConnectionID  /format:list') do set activeNet=%%F
rem for /f "tokens=2 delims==" %%F in ('wmic nic where "NetConnectionStatus=2 and AdapterTypeId=0 and PhysicalAdapter=TRUE and  NOT Name LIKE '%%VPN%%'" get  InterfaceIndex /format:list') do set activeNetID=%%F


for /f "tokens=1,2,3 skip=1 delims=," %%a in (
    'Powershell -C "Get-NetAdapter -Physical | Where-Object  { $_.Status -eq 'Up' } | Select-Object -Property Name,ifIndex  | ConvertTo-Csv  -NoTypeInformation"'
) Do (
	Set "activeNet=%%~a"
    Set "activeNetID=%%~b"
)


rem Print the result.
set /A "MAXMTU=!LASTGOOD! + !PACKETSIZE!"
echo Maximum MTU for !SERVER!: !MAXMTU! bytes.


echo The Command will now set MTU size to !MAXMTU! for Interface %activeNet% (ID: %activeNetID%) :
echo netsh interface ipv4 set subinterface %activeNetID%  mtu=!MAXMTU! store=persistent
echo Apply Commad now ?(y / n)
SET /p wahl=
if '%wahl%' == 'n' goto No
if '%wahl%' == 'y' goto Yes
Goto Ende
:No
echo Nothing Changed
goto Ende
:Yes
netsh interface ipv4 set subinterface %activeNetID%  mtu=!MAXMTU! store=persistent
:Ende


rem Export %MAXMTU% variable.
EndLocal
exit /B 0



:error
rem When something unexpected occurs.
EndLocal & set MAXMTU=-1
exit /B 1
