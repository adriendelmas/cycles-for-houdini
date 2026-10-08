@echo off
REM Starts Houdini with the Cycles delegate's log written to a file, so the
REM viewport timings (docs/TESTING.md, "Measuring interactivity") can be read
REM while Houdini runs. Pass a .hip path to open it, or none for an empty
REM session. The log goes to tests/scratch/cycles_viewport.log (ignored by git).
setlocal
set CYCLES_LOGGING=1
set CYCLES_LOGGING_LEVEL=info
if not exist "%~dp0..\scratch" mkdir "%~dp0..\scratch"
set CYCLES_LOG_FILE=%~dp0..\scratch\cycles_viewport.log
if exist "%CYCLES_LOG_FILE%" del "%CYCLES_LOG_FILE%"
start "" "E:\Side Effects Software\Houdini22.0.368\bin\houdini.exe" %*
endlocal
