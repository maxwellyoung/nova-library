#!/usr/bin/env python3
"""Add the Cloud shelf to a backed-up existing Nova theme, preserving its other changes."""
from pathlib import Path
import argparse
import shutil

ROOT=Path(__file__).resolve().parents[1]
def transform(text):
    edits=[
        ('    property var device: null','    readonly property var cloudBridge: typeof romCloud !== "undefined" && romCloud ? romCloud : null\n    property var device: null'),
        ('{ label: "Status", value: healthLabel() }','{ label: "Status", value: healthLabel() },\n                { label: "Cloud library", value: "Downloads and offline play" }'),
        ('else if (i === 5) loadHealth();','else if (i === 5) loadHealth();\n            else if (i === 6) { overlay = "cloud"; keyboardTimer.restart(); }'),
        ('        var k = api.keys;\n        if (event.isAutoRepeat','        var k = api.keys;\n        if (overlay === "cloud") {\n            if (!event.isAutoRepeat || k.isUp(event) || k.isDown(event)) cloudPanel.handleKey(event);\n            event.accepted = true;\n            return;\n        }\n        if (event.isAutoRepeat')
    ]
    if 'id: cloudPanel' in text:raise ValueError('Cloud shelf already present')
    for before,after in edits:
        if text.count(before)!=1:raise ValueError('Theme changed; inspect the current version before applying')
        text=text.replace(before,after,1)
    if not text.rstrip().endswith('}'):raise ValueError('Theme root is not complete')
    return text.rsplit('}',1)[0]+'''    CloudLibrary {
        id: cloudPanel
        anchors.fill: parent
        visible: root.overlay === "cloud"
        cloud: root.cloudBridge
        keyMap: api.keys
        ground: root.ground
        ink: root.ink
        quiet: root.quiet
        fontFamily: root.sans
        onClosed: { root.overlay = "settings"; root.panelIndex = 6; root.forceActiveFocus(); }
    }
}\n'''
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('theme',type=Path);p.add_argument('--backup',type=Path,required=True);a=p.parse_args()
    try:
        target=a.theme/'theme.qml';updated=transform(target.read_text())
        if a.backup.exists() or (a.theme/'CloudLibrary.qml').exists():raise ValueError('Backup or Cloud component already exists')
        a.backup.mkdir(parents=True);shutil.copy2(target,a.backup/'theme.qml')
        shutil.copy2(ROOT/'theme/CloudLibrary.qml',a.theme/'CloudLibrary.qml')
        target.write_text(updated)
        print('Cloud shelf added; original theme preserved in the selected backup.')
    except (ValueError,OSError) as e:p.exit(1,str(e)+'\n')
