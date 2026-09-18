-- iPhone 镜像窗口操作
-- 用法: osascript scripts/mirror.applescript <命令>

on run argv
	if (count of argv) is 0 then
		return "ERR:no-command"
	end if
	set cmd to item 1 of argv
	try
		if cmd is "open" then
			return my openMirror()
		else if cmd is "running" then
			return my isRunning()
		else if cmd is "window" then
			return my hasWindow()
		else if cmd is "bounds" then
			return my windowBounds()
		else if cmd is "front" then
			return my bringFront()
		else if cmd is "larger" then
			return my makeLarger()
		else if cmd is "actual-size" then
			return my actualSize()
		else if cmd is "set-size" then
			if (count of argv) < 3 then
				return "ERR:need-width-height"
			end if
			set targetW to item 2 of argv as integer
			set targetH to item 3 of argv as integer
			return my setWindowSize(targetW, targetH)
		else if cmd is "click-center" then
			return my clickCenter()
		else if cmd is "type-pin" then
			return my typePin()
		else
			return "ERR:unknown-command"
		end if
	on error errMsg
		return "ERR:" & errMsg
	end try
end run

on openMirror()
	try
		tell application "iPhone Mirroring" to activate
	end try
	delay 0.8
	return "OK"
end openMirror

on processName()
	tell application "System Events"
		if exists process "iPhone Mirroring" then
			return "iPhone Mirroring"
		end if
		if exists process "iPhone镜像" then
			return "iPhone镜像"
		end if
	end tell
	return ""
end processName

on frontMirror()
	set pname to my processName()
	if pname is "" then
		return false
	end if
	tell application "System Events"
		tell process pname
			set frontmost to true
		end tell
	end tell
	return true
end frontMirror

on isRunning()
	if my processName() is "" then
		return "no"
	end if
	return "yes"
end isRunning

on hasWindow()
	set pname to my processName()
	if pname is "" then
		return "no"
	end if
	tell application "System Events"
		tell process pname
			if (count of windows) > 0 then
				return "yes"
			else
				return "no"
			end if
		end tell
	end tell
end hasWindow

on windowBounds()
	set pname to my processName()
	if pname is "" then
		return "ERR:not-running"
	end if
	tell application "System Events"
		tell process pname
			if (count of windows) is 0 then
				return "ERR:no-window"
			end if
			set p to position of window 1
			set s to size of window 1
			return (item 1 of p as integer as text) & "," & (item 2 of p as integer as text) & "," & (item 1 of s as integer as text) & "," & (item 2 of s as integer as text)
		end tell
	end tell
end windowBounds

on bringFront()
	if my frontMirror() then
		return "OK"
	end if
	try
		tell application "iPhone Mirroring" to activate
	end try
	delay 0.2
	if my frontMirror() then
		return "OK"
	end if
	return "ERR:not-running"
end bringFront

on makeLarger()
	if not my frontMirror() then
		return "ERR:not-running"
	end if
	delay 0.15
	set pname to my processName()
	tell application "System Events"
		tell process pname
			try
				click menu item "Larger" of menu "View" of menu bar 1
				return "OK"
			end try
			try
				click menu item "放大" of menu "显示" of menu bar 1
				return "OK"
			end try
			keystroke "=" using {command down}
			return "OK-key"
		end tell
	end tell
end makeLarger

on setWindowSize(targetW, targetH)
	if targetW < 200 or targetH < 200 then
		return "ERR:too-small"
	end if
	if not my frontMirror() then
		return "ERR:not-running"
	end if
	delay 0.1
	set pname to my processName()
	tell application "System Events"
		tell process pname
			if (count of windows) is 0 then
				return "ERR:no-window"
			end if
			set p to position of window 1
			try
				set value of attribute "AXSize" of window 1 to {targetW, targetH}
			end try
			try
				set size of window 1 to {targetW, targetH}
			end try
			set position of window 1 to p
			delay 0.2
			set s to size of window 1
			return (item 1 of s as integer as text) & "," & (item 2 of s as integer as text)
		end tell
	end tell
end setWindowSize

on actualSize()
	if not my frontMirror() then
		return "ERR:not-running"
	end if
	delay 0.15
	set pname to my processName()
	tell application "System Events"
		tell process pname
			try
				click menu item "Actual Size" of menu "View" of menu bar 1
				return "OK"
			end try
			try
				click menu item "实际大小" of menu "显示" of menu bar 1
				return "OK"
			end try
			keystroke "0" using {command down}
			return "OK-key"
		end tell
	end tell
end actualSize

on clickCenter()
	tell application "System Events"
		if not (exists process "iPhone Mirroring") then
			return "ERR:not-running"
		end if
		tell process "iPhone Mirroring"
			set frontmost to true
			if (count of windows) is 0 then
				return "ERR:no-window"
			end if
			set p to position of window 1
			set s to size of window 1
			set cx to (item 1 of p) + (item 1 of s) / 2
			set cy to (item 2 of p) + (item 2 of s) / 2
		end tell
		delay 0.2
		click at {cx as integer, cy as integer}
	end tell
	return "OK"
end clickCenter

on typePin()
	set pin to do shell script "security find-generic-password -a " & quoted form of (short user name of (system info)) & " -s game-plugin.iphone-passcode -w"
	if pin is "" then
		return "ERR:empty-pin"
	end if
	tell application "System Events"
		if not (exists process "iPhone Mirroring") then
			return "ERR:not-running"
		end if
		tell process "iPhone Mirroring"
			set frontmost to true
			delay 0.3
			repeat with c in characters of pin
				keystroke c
				delay 0.08
			end repeat
		end tell
	end tell
	return "OK"
end typePin
