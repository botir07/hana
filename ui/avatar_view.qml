import QtQuick 2.15
import QtQuick3D 6.5

Item {
    width: 400
    height: 400
    property url modelPath
    property real spin: 0

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            clearColor: "#1c1c1c"
            backgroundMode: SceneEnvironment.Color
        }

        PerspectiveCamera {
            position: Qt.vector3d(0, 1.5, 4.0)
            eulerRotation.x: -10
        }

        DirectionalLight {
            eulerRotation.x: -20
            eulerRotation.y: 45
            brightness: 1.2
        }

        Model {
            source: modelPath
            scale: Qt.vector3d(1, 1, 1)
            eulerRotation.y: spin
        }
    }

    NumberAnimation on spin {
        from: 0
        to: 360
        duration: 12000
        loops: Animation.Infinite
    }
}
