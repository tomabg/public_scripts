# public_scripts
repo with public scripts

set-optimal-MTU-for-VPN.bat .....will find out and set MTU size...this is needed for IKE VPN and Provider Vodafone Cable with DSLite


Usage for DownloadFilesFromRepo.ps1:

```PowerShell
iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/tomabg/public_scripts/master/DownloadFilesFromRepo.ps1')) 
DownloadFilesFromRepo -Owner tomabg -Repository SS.PowerShell -Path SS.PowerShell/bin/Debug -DestinationPath (Get-Module -ListAvailable SS.PowerShell).path.TrimEnd('SS.PowerShell.psd1')
```

