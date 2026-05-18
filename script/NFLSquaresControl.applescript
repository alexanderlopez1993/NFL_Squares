property controlScript : "/Users/alexanderlopez/Projects/NFL_Squares/script/nfl_squares_server.sh"
property shareScript : "/Users/alexanderlopez/Projects/NFL_Squares/script/nfl_squares_public_share.sh"
property appUrl : "http://127.0.0.1:8000/boards/dashboard/"

on run
	set rawStatus to do shell script quoted form of controlScript & " status"
	set rawShareStatus to do shell script quoted form of shareScript & " status"
	set serverRunning to rawStatus starts with "running:"
	set shareRunning to rawShareStatus starts with "running:"
	
	if serverRunning then
		set statusLabel to "Server is running."
	else
		set statusLabel to "Server is stopped."
	end if
	if shareRunning then
		set statusLabel to statusLabel & return & "Public share is running."
	else
		set statusLabel to statusLabel & return & "Public share is stopped."
	end if
	
	set picked to choose from list {"Open Dashboard", "Start Server", "Start Public Share", "Stop Public Share", "Stop Server", "Status"} with title "NFL Squares Control" with prompt statusLabel default items {"Open Dashboard"}
	if picked is false then return
	set actionName to item 1 of picked
	
	if actionName is "Open Dashboard" then
		my openDashboard()
	else if actionName is "Start Server" then
		my startServer()
	else if actionName is "Start Public Share" then
		my startPublicShare()
	else if actionName is "Stop Public Share" then
		my stopPublicShare()
	else if actionName is "Stop Server" then
		my stopServer()
	else if actionName is "Status" then
		display dialog statusLabel buttons {"OK"} default button "OK"
	end if
end run

on openDashboard()
	set rawStatus to do shell script quoted form of controlScript & " status"
	if rawStatus starts with "running:" then
		do shell script "open " & quoted form of appUrl
	else
		set startChoice to button returned of (display dialog "The NFL Squares server is off." buttons {"Cancel", "Start Server"} default button "Start Server")
		if startChoice is "Start Server" then
			my startServer()
			do shell script "open " & quoted form of appUrl
		end if
	end if
end openDashboard

on startServer()
	set enteredPassword to text returned of (display dialog "Enter the local admin password to start NFL Squares." default answer "" hidden answer true buttons {"Cancel", "Start"} default button "Start")
	try
		set outputText to do shell script "NFL_SQUARES_ADMIN_PASSWORD=" & quoted form of enteredPassword & " " & quoted form of controlScript & " start"
		display dialog outputText buttons {"Open Dashboard", "OK"} default button "Open Dashboard"
		if button returned of result is "Open Dashboard" then
			do shell script "open " & quoted form of appUrl
		end if
	on error errorMessage number errorNumber
		if errorNumber is 44 then
			display dialog "The local admin password did not match." buttons {"OK"} default button "OK" with icon caution
		else if errorNumber is 45 then
			display dialog "No local admin password was found in Keychain." buttons {"OK"} default button "OK" with icon caution
		else
			display dialog errorMessage buttons {"OK"} default button "OK" with icon caution
		end if
	end try
end startServer

on stopServer()
	set shareOutput to do shell script quoted form of shareScript & " stop"
	set outputText to do shell script quoted form of controlScript & " stop"
	display dialog shareOutput & return & outputText buttons {"OK"} default button "OK"
end stopServer

on startPublicShare()
	set enteredPassword to text returned of (display dialog "Enter the local admin password to start NFL Squares public sharing." default answer "" hidden answer true buttons {"Cancel", "Start Public Share"} default button "Start Public Share")
	try
		set outputText to do shell script "NFL_SQUARES_ADMIN_PASSWORD=" & quoted form of enteredPassword & " " & quoted form of shareScript & " start"
		display dialog outputText buttons {"Open Public Dashboard", "OK"} default button "Open Public Dashboard"
		if button returned of result is "Open Public Dashboard" then
			do shell script quoted form of shareScript & " open"
		end if
	on error errorMessage number errorNumber
		if errorNumber is 44 then
			display dialog "The local admin password did not match." buttons {"OK"} default button "OK" with icon caution
		else if errorNumber is 45 then
			display dialog "No local admin password was found in Keychain." buttons {"OK"} default button "OK" with icon caution
		else if errorNumber is 46 then
			display dialog "cloudflared is not installed. Install Cloudflare Tunnel, then run Start Public Share again." buttons {"OK"} default button "OK" with icon caution
		else
			display dialog errorMessage buttons {"OK"} default button "OK" with icon caution
		end if
	end try
end startPublicShare

on stopPublicShare()
	set outputText to do shell script quoted form of shareScript & " stop"
	display dialog outputText buttons {"OK"} default button "OK"
end stopPublicShare
