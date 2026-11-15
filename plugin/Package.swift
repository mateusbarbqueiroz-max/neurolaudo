// swift-tools-version:5.9
//
// Conferência em Linux (e em qualquer máquina com Swift): compila o núcleo e a
// "cola" do complemento contra uma IMITAÇÃO do IsiXPluginKit e roda os testes.
// O complemento de verdade é compilado pelo Xcode (NeuroLaudo.xcodeproj) em
// macOS; este pacote não participa dele. A pasta UI (AppKit) fica de fora.
import PackageDescription

let package = Package(
    name: "NeuroLaudoCheck",
    targets: [
        .target(name: "IsiXPluginKit", path: "LinuxCheck/IsiXPluginKitStub"),
        .target(name: "NeuroLaudo", dependencies: ["IsiXPluginKit"], path: "NeuroLaudo/Sources", exclude: ["UI"],
                swiftSettings: [.unsafeFlags(["-strict-concurrency=complete"])]),
        .testTarget(name: "NeuroLaudoTests", dependencies: ["NeuroLaudo", "IsiXPluginKit"], path: "Tests/NeuroLaudoTests"),
    ]
)
