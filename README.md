# public_scripts
## repo with public scripts


### Usage for DownloadFilesFromRepo.ps1:

```PowerShell
iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/tomabg/public_scripts/master/DownloadFilesFromRepo.ps1')) 
DownloadFilesFromRepo -Owner tomabg -Repository SS.PowerShell -Path SS.PowerShell/bin/Debug -DestinationPath (Get-Module -ListAvailable SS.PowerShell).path.TrimEnd('SS.PowerShell.psd1')
```

### One-Liner for set-optimal-MTU-for-VPN.bat

:information_source: | set-optimal-MTU-for-VPN.bat .....will find out and set MTU size...this is needed for IKEv2 VPN and Provider Vodafone Cable with DSLite ...
Download the batch file and execute in an administrative cmd
:---: | :---

open cmd as Admin and copy below command

```cmd
bitsadmin /transfer Download-MTU-Skript /download /priority normal https://raw.githubusercontent.com/tomabg/public_scripts/master/set-optimal-MTU-for-VPN.bat %TEMP%\set-optimal-MTU-for-VPN.bat && %TEMP%\set-optimal-MTU-for-VPN.bat
```
