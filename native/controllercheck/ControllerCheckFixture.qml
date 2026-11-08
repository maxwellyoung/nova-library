import QtQuick 2.15
import QtQuick.Window 2.15
Window {
    id: checkWindow
    width: 1280; height: 960; visible: true; color: "#181b20"
    title: "Nova controller check"
    property var diagnostic: controllerCheck.state
    property int renderedDeviceCount: deviceRows.count
    Text { x: 36; y: 28; width: parent.width-72; color: "#f4f0e8"; font.pixelSize: 32; text: "Controller check" }
    Text { x: 36; y: 76; width: parent.width-72; color: "#d1bd87"; font.pixelSize: 20
        text: checkWindow.diagnostic.method === "injected" ? "Injected fixture · no physical controller proof" : "Observed native events · physical acceptance remains open" }
    Text { x: 36; y: 112; width: parent.width-72; color: "#bbc2cc"; font.pixelSize: 18
        text: "Select is a controller button. Back is a separate system key; its device identity is unavailable." }
    Flickable {
        x:36; y:160; width:parent.width-72; height:parent.height-y-90; clip:true; contentHeight:body.height
        Column { id:body; width:parent.width; spacing:20
            Repeater { id: deviceRows; model: checkWindow.diagnostic.devices
                Column { width:body.width; spacing:10; property var device:modelData
                    Text { color:"#f4f0e8"; font.pixelSize:24; text:"Qt device "+device.qtDeviceId+" · "+(device.connected?"Connected":"Disconnected") }
                    Flow { width:parent.width; spacing:10
                        Repeater { model:Object.keys(device.buttons)
                            Rectangle { width:130; height:52; color:device.buttons[modelData].raw>0?"#517159":"#2b3038"; radius:5
                                Text { anchors.centerIn:parent; color:"#f4f0e8"; font.pixelSize:18; text:modelData+ (device.buttons[modelData].seen ? " ✓" : " ·") }
                            }
                        }
                    }
                    Repeater { model:Object.keys(device.axes)
                        Text { color:"#dbe1e8"; font.pixelSize:20; property var a:device.axes[modelData]
                            text:modelData+"   raw "+a.raw.toFixed(3)+"   filtered "+a.filtered.toFixed(3)+"   observed range "+(a.seen?a.minimum.toFixed(3)+" … "+a.maximum.toFixed(3):"Not sampled") }
                    }
                    Repeater { model:["l2","r2"]
                        Text { color:"#dbe1e8"; font.pixelSize:20; property var t:device.triggers[modelData]
                            text:modelData+" pressure   "+t.raw.toFixed(3)+"   "+(t.seen?"Qt value observed; hardware resolution unverified":"Not sampled") }
                    }
                }
            }
            Text { color:"#f4f0e8"; font.pixelSize:22; text: "System Back: "+(checkWindow.diagnostic.systemBack.raw>0?"Pressed":checkWindow.diagnostic.systemBack.seen?"Neutral":"Not observed") }
            Text { color:"#bbc2cc"; font.pixelSize:18; text:"Duplicates "+checkWindow.diagnostic.duplicateEvents+" · rejected "+checkWindow.diagnostic.rejectedEvents+" · resets do not count as releases" }
            Text { visible:!checkWindow.diagnostic.devices.length; color:"#f4f0e8"; font.pixelSize:24; text:"No Qt gamepad connection observed. Axes are unavailable until a native device appears." }
        }
    }
    Text { x:36; y:parent.height-56; width:parent.width-72; color:"#bbc2cc"; font.pixelSize:18; text:"Private diagnostic · preview and exact-digest export through the host API · nothing sent" }
    Item { focus:true; Keys.onPressed: { if(event.key===Qt.Key_Back) event.accepted=true } }
}
