on run argv
 set inputPath to item 1 of argv
 set outputPath to item 2 of argv
 tell application "Microsoft Word"
  open (POSIX file inputPath)
  set taskDoc to active document
  if (posix full name of taskDoc) is not inputPath then error "Unexpected active document; export stopped"
  repaginate taskDoc
  repeat with taskField in (get fields of taskDoc)
   update field taskField
  end repeat
  save taskDoc
  save as taskDoc file name outputPath file format format PDF
  close taskDoc saving no
 end tell
end run
