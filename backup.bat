@echo off
set fecha=%date:~-4,4%%date:~-10,2%%date:~-7,2%
set hora=%time:~0,2%%time:~3,2%
set hora=%hora: =0%

"C:\mongo-tools\bin\mongodump.exe" ^
  --uri="mongodb://localhost:27017" ^
  --db=vehiculos_db ^
  --out="D:\Googledrive Mario\proyecto-flask\backups\%fecha%_%hora%"