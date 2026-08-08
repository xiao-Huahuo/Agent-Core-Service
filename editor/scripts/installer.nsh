!include nsDialogs.nsh
!include LogicLib.nsh

!ifndef BUILD_UNINSTALLER

Var desktopShortcutCheckbox
Var desktopShortcutSelected

!macro customPageAfterChangeDir
  Page custom desktopShortcutPageCreate desktopShortcutPageLeave
!macroend

Function desktopShortcutPageCreate
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 24u "Choose optional shortcuts"
  Pop $0
  ${NSD_CreateCheckbox} 0 30u 100% 12u "Create a desktop shortcut"
  Pop $desktopShortcutCheckbox
  ${NSD_SetState} $desktopShortcutCheckbox ${BST_CHECKED}
  nsDialogs::Show
FunctionEnd

Function desktopShortcutPageLeave
  ${NSD_GetState} $desktopShortcutCheckbox $desktopShortcutSelected
FunctionEnd

!macro customInstall
  File /oname=$INSTDIR\MetaWeave.ico "${MUI_ICON}"
  ${If} $desktopShortcutSelected == ${BST_CHECKED}
    CreateShortCut "$DESKTOP\${SHORTCUT_NAME}.lnk" "$appExe" "$appExe" 0 "" "" "${APP_DESCRIPTION}"
    ClearErrors
    System::Call 'shell32::SHChangeNotify(i 0x8000000, i 0, i 0, i 0)'
  ${EndIf}
!macroend

!endif
