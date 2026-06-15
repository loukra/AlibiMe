#if canImport(SwiftUI)
import SwiftUI

/// Structured editor for a new custom template. Every input is a dropdown,
/// toggle, or bounded control — no free-form prompt/SMS text. The backend
/// composes the believable wording from the chosen persona/reason/urgency.
public struct CustomTemplateEditorView: View {
    @Bindable var vm: CustomTemplateEditorViewModel
    let onClose: () -> Void
    let onCreated: (TemplateSummary) -> Void

    public init(vm: CustomTemplateEditorViewModel,
                onClose: @escaping () -> Void,
                onCreated: @escaping (TemplateSummary) -> Void) {
        self.vm = vm
        self.onClose = onClose
        self.onCreated = onCreated
    }

    public var body: some View {
        NavigationStack {
            Form {
                if vm.options == nil {
                    Section { HStack { Spacer(); ProgressView(); Spacer() } }
                } else if let options = vm.options {
                    editorSections(options)
                }
                if let error = vm.errorMessage {
                    Section { ErrorBanner(error) }
                }
            }
            .bcClearScrollBackground()
            .bcScreenBackground()
            .navigationTitle("New Template")
            .bcInlineNavTitle()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onClose)
                }
                ToolbarItem(placement: .confirmationAction) {
                    if vm.isSubmitting {
                        ProgressView()
                    } else {
                        Button("Save") {
                            Task { if let created = await vm.submit() { onCreated(created) } }
                        }
                        .disabled(!vm.canSubmit)
                    }
                }
            }
            .task { if vm.options == nil { await vm.load() } }
        }
    }

    @ViewBuilder
    private func editorSections(_ options: TemplateOptions) -> some View {
        Section("Name") {
            TextField("Template name", text: $vm.draft.displayName)
            TextField("Description (optional)", text: $vm.draft.description)
        }
        Section("Who & why") {
            Picker("Persona", selection: $vm.draft.persona) {
                ForEach(options.personas) { Text($0.label).tag($0.code) }
            }
            Picker("Reason", selection: $vm.draft.reason) {
                ForEach(options.reasons) { Text($0.label).tag($0.code) }
            }
            Picker("Category", selection: $vm.draft.category) {
                ForEach(options.categories, id: \.self) { Text($0.capitalized).tag($0) }
            }
            Picker("Urgency", selection: $vm.draft.urgency) {
                ForEach(options.urgencies, id: \.self) { Text($0.capitalized).tag($0) }
            }
        }
        Section("Channels") {
            ForEach(options.channels) { channel in
                Toggle(channel.title, isOn: Binding(
                    get: { vm.draft.channels.contains(channel) },
                    set: { vm.toggle(channel, on: $0) }
                ))
            }
        }
        if vm.draft.channels.contains(.call) {
            Section("Call options") {
                Picker("Voice", selection: $vm.draft.voiceStyle) {
                    ForEach(options.voiceStyles, id: \.self) { Text($0.capitalized).tag($0) }
                }
                Stepper(
                    "Max length: \(vm.draft.callMaxSeconds)s",
                    value: $vm.draft.callMaxSeconds,
                    in: options.callSecondsMin...options.callSecondsMax,
                    step: 10
                )
            }
        }
        Section {
            Text("The wording is generated safely from your choices — you can't type custom call or text content.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }
}

struct CustomTemplateEditorView_Previews: PreviewProvider {
    static var previews: some View {
        CustomTemplateEditorView(vm: CustomTemplateEditorViewModel(service: MockTemplateService()),
                                 onClose: {}, onCreated: { _ in })
    }
}
#endif
