import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15

Window {
    id: root
    visible: true
    width: 1000
    height: 600
    color: "black"
    title: "FL Foreclosure County Scraper"


    property var logoLines: [
        "███████╗██╗      ██████╗ ██████╗ ██╗██████╗  █████╗     ███████╗ ██████╗ ██████╗ ███████╗ ██████╗██╗      ██████╗  ███████╗██╗   ██╗██████╗ ███████╗",
        "██╔════╝██║     ██╔═══██╗██╔══██╗██║██╔══██╗██╔══██╗    ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔════╝██║     ██╔═══██╗ ██╔════╝██║   ██║██╔══██╗██╔════╝",
        "█████╗  ██║     ██║   ██║██████╔╝██║██║  ██║███████║    █████╗  ██║   ██║██████╔╝█████╗  ██║     ██║     ██║   ██║ ███████╗██║   ██║██████╔╝█████╗  ",
        "██╔══╝  ██║     ██║   ██║██╔══██╗██║██║  ██║██╔══██║    ██╔══╝  ██║   ██║██╔══██╗██╔══╝  ██║     ██║     ██║   ██║ ╚════██║██║   ██║██╔══██╗██╔══╝  ",
        "██║     ███████╗╚██████╔╝██║  ██║██║██████╔╝██║  ██║    ██║     ╚██████╔╝██║  ██║███████╗╚██████╗███████╗╚██████╔╝ ███████║╚██████╔╝██║  ██║███████╗",
        "╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝    ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝╚══════╝ ╚═════╝  ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝"
    ]

    Column {
        id: asciiText
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 30
        spacing: 0

        Repeater {
            model: logoLines.length
            delegate: Row {
                spacing: 0.5
                property string line: logoLines[index]

                Repeater {
                    model: line.length
                    delegate: Text {
                        text: line.charAt(index)
                        color: "white"
                        font.pixelSize: 10
                        font.family: "Consolas"
                        y: 0
                        opacity: 0

                        SequentialAnimation on y {
                            running: true
                            loops: 1
                            PauseAnimation { duration: index * 25 }
                            PropertyAnimation { to: -5; duration: 150; easing.type: Easing.OutQuad }
                            PropertyAnimation { to: 0; duration: 200; easing.type: Easing.InQuad }
                        }

                        SequentialAnimation on opacity {
                            running: true
                            loops: 1
                            PauseAnimation { duration: index * 25 }
                            PropertyAnimation { to: 1; duration: 300 }
                        }
                    }
                }
            }
        }
    }

    Timer {
        id: startScraperTimer
        interval: 4500
        running: true
        repeat: false
        onTriggered: {
            terminalOutput.visible = true
            backend.start_scraping()
        }
    }

    Rectangle {
        id: terminalOutput
        visible: false
        anchors.top: asciiText.bottom
        anchors.topMargin: 20
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        color: "#000000B3"

        ScrollView {    
            id: scrollview
            anchors.fill: parent    
            anchors.margins: 10
            
            Column {
                id: terminalColumn
                spacing: 4
                width: parent.width

                // Main terminal text with typing animation
                Text {
                    id: terminalText
                    color: "white"
                    font.family: "Consolas"
                    font.pointSize: 12
                    wrapMode: Text.Wrap
                    text: ""

                    property string fullText: ""
                    property int currentIndex: 0

                    Timer {
                        id: typingTimer1
                        interval: 15
                        repeat: true
                        running: false
                        onTriggered: {
                            if (terminalText.currentIndex < terminalText.fullText.length) {
                                terminalText.text += terminalText.fullText.charAt(terminalText.currentIndex)
                                terminalText.currentIndex++
                                
                                // ✅ Delay scroll to allow layout to settle (avoid glitch)
                                Qt.callLater(() => {
                                    // Smooth scroll down only if overflowed
                                    if (scrollview.contentItem.contentHeight > scrollview.height) {
                                        scrollview.contentItem.contentY = scrollview.contentItem.contentHeight - scrollview.height
                                    }
                                })
                            } else {
                                typingTimer1.stop()
                                backend.notify_typing_done()
                            }
                        }
                    }
                }

                // Retry countdown text with typing + live number update
                Text {
                    id: retryCountdownText
                    color: "white"
                    font.family: "Consolas"
                    font.pointSize: 12
                    wrapMode: Text.NoWrap
                    visible: false
                    text: ""

                    property string staticText: ""
                    property int typingIndex: 0
                    property int countdownValue: 0
                }
            }
        }

        // Moved timers outside retryCountdownText for proper access:
        Timer {
            id: typingTimer
            interval: 20
            running: false
            repeat: true
            onTriggered: {
                if (retryCountdownText.typingIndex < retryCountdownText.staticText.length) {
                    retryCountdownText.text += retryCountdownText.staticText.charAt(retryCountdownText.typingIndex)
                    retryCountdownText.typingIndex++
                } else {
                    typingTimer.stop()
                    retryCountdownText.text += " " + retryCountdownText.countdownValue + " sec"
                    countdownTimer.start()
                }
            }
        }

        Timer {
            id: countdownTimer
            interval: 1000
            running: false
            repeat: true
            onTriggered: {
                if (retryCountdownText.countdownValue > 0) {
                    retryCountdownText.countdownValue--
                    retryCountdownText.text = retryCountdownText.staticText + " " + retryCountdownText.countdownValue + " sec"
                } else {
                    countdownTimer.stop()
                    retryCountdownText.visible = false
                    retryCountdownText.text = ""
                }
            }
        }

        Connections {
            target: stream
            function onCharWritten(c) {
                if (c === "[!] Retrying in (static)\n") {
                    retryCountdownText.visible = true
                    retryCountdownText.staticText = "🔄 Retrying in"
                    retryCountdownText.countdownValue = 30
                    retryCountdownText.text = ""
                    retryCountdownText.typingIndex = 0
                    countdownTimer.stop()
                    typingTimer.start()
                    return
                }

                if (c.startsWith("[!] Retrying countdown ")) {
                    var parts = c.split(" ")
                    var newVal = parseInt(parts[2])
                    if (!isNaN(newVal)) {
                        retryCountdownText.countdownValue = newVal
                        retryCountdownText.text = retryCountdownText.staticText + " " + retryCountdownText.countdownValue + " sec"
                    }
                    return
                }

                if (c.startsWith("[✓]")) {
                    countdownTimer.stop()
                    typingTimer.stop()
                    retryCountdownText.visible = false
                    retryCountdownText.text = ""
                    return
                }

                if (c.includes("\r")) {
                    return
                }

                terminalText.fullText += c
                if (!typingTimer1.running)
                    typingTimer1.start()
            }
        }

        Component.onCompleted: {
            Qt.callLater(() => forceActiveFocus())
        }
    }

    onClosing: {
        backend.force_quit()
    }
}

