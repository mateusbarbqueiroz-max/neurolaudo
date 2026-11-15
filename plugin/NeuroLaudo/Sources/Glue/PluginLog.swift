//  NeuroLaudo — registro do complemento no log do macOS.
//
//  Para ler no Mac (Terminal):
//    log show --last 10m --predicate 'subsystem == "app.neurolaudo.isixplugin"'

#if canImport(os)
import os
#endif
import Foundation

enum PluginLog {
    static let subsystem = "app.neurolaudo.isixplugin"

    /// Uma linha no log do sistema. Em Linux (testes) não faz nada.
    static func note(_ message: String) {
        #if canImport(os)
        Logger(subsystem: subsystem, category: "plugin").notice("\(message, privacy: .public)")
        #endif
    }
}
