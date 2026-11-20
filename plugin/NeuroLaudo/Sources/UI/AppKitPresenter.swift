//  NeuroLaudo — telas do complemento, com AppKit. Só compila em macOS.
//
//  Este arquivo NÃO é conferido em Linux (não há AppKit lá): a primeira
//  compilação de verdade é a do servidor Mac. Por isso é curto e convencional.

#if canImport(AppKit)
import AppKit

@MainActor final class AppKitPresenter: Presenting {
    private var aspectsPanel: AspectsPanelController?

    /// Copia um texto para a área de transferência, para colar no laudo.
    static func copy(_ text: String) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
    }

    /// Número digitado pelo usuário, aceitando vírgula decimal; 0 se não for número.
    static func parseNumber(_ text: String) -> Double {
        Double(text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")) ?? 0
    }

    func show(_ outcome: MeasureOutcome, in window: NSWindow?) {
        let alert = NSAlert()
        alert.messageText = outcome.title
        if outcome.text.count > 900 {
            // Texto longo (lista de séries, por exemplo): numa área que rola, para o aviso caber na tela.
            alert.informativeText = "Use Copiar para levar o texto inteiro."
            let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 560, height: 340))
            scroll.hasVerticalScroller = true
            scroll.borderType = .bezelBorder
            let view = NSTextView(frame: NSRect(origin: .zero, size: scroll.contentSize))
            view.isEditable = false
            view.isSelectable = true
            view.font = NSFont.monospacedSystemFont(ofSize: NSFont.smallSystemFontSize, weight: .regular)
            // Cresce para baixo com o texto, para a área rolar até o fim.
            view.minSize = NSSize(width: 0, height: scroll.contentSize.height)
            view.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
            view.isVerticallyResizable = true
            view.isHorizontallyResizable = false
            view.textContainer?.containerSize = NSSize(width: scroll.contentSize.width, height: CGFloat.greatestFiniteMagnitude)
            view.textContainer?.widthTracksTextView = true
            view.string = outcome.text
            view.autoresizingMask = [.width]
            scroll.documentView = view
            alert.accessoryView = scroll
        } else {
            alert.informativeText = outcome.text
        }
        alert.addButton(withTitle: "Copiar")
        alert.addButton(withTitle: "Fechar")
        let text = outcome.text
        if let window, window.isVisible, window.attachedSheet == nil {
            alert.beginSheetModal(for: window) { response in
                guard response == .alertFirstButtonReturn else { return }
                Task { @MainActor in AppKitPresenter.copy(text) }
            }
        } else if alert.runModal() == .alertFirstButtonReturn {
            AppKitPresenter.copy(text)
        }
    }

    func askSliceCount(intervalMM: Double, in window: NSWindow?, completion: @escaping @MainActor @Sendable (Double?) -> Void) {
        let alert = NSAlert()
        alert.messageText = "Volume de hematoma (ABC/2)"
        alert.informativeText = "Em quantos cortes o hematoma aparece? "
            + "O intervalo entre cortes desta série é de \(Fmt.mm(intervalMM))."
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 120, height: 24))
        field.stringValue = "1"
        alert.accessoryView = field
        alert.addButton(withTitle: "Calcular")
        alert.addButton(withTitle: "Cancelar")
        alert.window.initialFirstResponder = field
        if let window, window.isVisible, window.attachedSheet == nil {
            alert.beginSheetModal(for: window) { response in
                Task { @MainActor in
                    completion(response == .alertFirstButtonReturn ? AppKitPresenter.parseNumber(field.stringValue) : nil)
                }
            }
        } else {
            let response = alert.runModal()
            completion(response == .alertFirstButtonReturn ? AppKitPresenter.parseNumber(field.stringValue) : nil)
        }
    }

    func showAspects() {
        if aspectsPanel == nil { aspectsPanel = AspectsPanelController() }
        aspectsPanel?.showWindow(nil)
        aspectsPanel?.window?.makeKeyAndOrderFront(nil)
    }

    func closeAll() {
        aspectsPanel?.close()
        aspectsPanel = nil
    }
}

/// Painel flutuante com as dez regiões do ASPECTS e a frase pronta para o laudo.
@MainActor final class AspectsPanelController: NSWindowController {
    private var boxes: [(code: String, button: NSButton)] = []
    private let sidePopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let scoreLabel = NSTextField(labelWithString: "ASPECTS 10")
    private let sentenceLabel = NSTextField(wrappingLabelWithString: "")

    init() {
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 440, height: 400),
                            styleMask: [.titled, .closable, .utilityWindow], backing: .buffered, defer: true)
        panel.title = "ASPECTS"
        panel.isFloatingPanel = true
        panel.hidesOnDeactivate = false
        super.init(window: panel)
        buildContent(in: panel)
        update()
        panel.center()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) não é usado")
    }

    private func buildContent(in panel: NSPanel) {
        sidePopup.addItems(withTitles: ["Território da ACM direita", "Território da ACM esquerda"])
        sidePopup.target = self
        sidePopup.action = #selector(changed(_:))

        let left = NSStackView()
        let right = NSStackView()
        for column in [left, right] {
            column.orientation = .vertical
            column.alignment = .leading
            column.spacing = 6
        }
        for (index, region) in Aspects.regions.enumerated() {
            let button = NSButton(checkboxWithTitle: "\(region.code) — \(region.name)", target: self, action: #selector(changed(_:)))
            boxes.append((region.code, button))
            (index < 5 ? left : right).addArrangedSubview(button)
        }
        let columns = NSStackView(views: [left, right])
        columns.orientation = .horizontal
        columns.alignment = .top
        columns.spacing = 24

        scoreLabel.font = NSFont.boldSystemFont(ofSize: 20)
        sentenceLabel.preferredMaxLayoutWidth = 400
        sentenceLabel.isSelectable = true

        let copyButton = NSButton(title: "Copiar frase", target: self, action: #selector(copySentence(_:)))
        let clearButton = NSButton(title: "Limpar", target: self, action: #selector(clear(_:)))
        let buttons = NSStackView(views: [copyButton, clearButton])
        buttons.orientation = .horizontal
        buttons.spacing = 12

        let hint = NSTextField(labelWithString: "Marque as regiões com sinais de isquemia precoce:")
        let stack = NSStackView(views: [sidePopup, hint, columns, scoreLabel, sentenceLabel, buttons])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        panel.contentView = stack
    }

    private var affected: Set<String> {
        Set(boxes.filter { $0.button.state == .on }.map(\.code))
    }

    private var side: BrainSide {
        sidePopup.indexOfSelectedItem == 1 ? .left : .right
    }

    private func update() {
        scoreLabel.stringValue = "ASPECTS \(10 - affected.count)"
        sentenceLabel.stringValue = (try? Aspects.summary(affected: affected, side: side)) ?? ""
    }

    @objc private func changed(_ sender: Any?) {
        update()
    }

    @objc private func copySentence(_ sender: Any?) {
        AppKitPresenter.copy(sentenceLabel.stringValue)
    }

    @objc private func clear(_ sender: Any?) {
        for box in boxes { box.button.state = .off }
        update()
    }
}
#endif
