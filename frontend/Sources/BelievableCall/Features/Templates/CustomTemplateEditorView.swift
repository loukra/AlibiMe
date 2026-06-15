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
        // Step 1 — scenario core
        Section("Name") {
            TextField("Template name", text: $vm.draft.displayName)
            TextField("Description (optional)", text: $vm.draft.description)
        }
        Section("Scenario") {
            optionPicker("Persona", $vm.draft.persona, options.personas)
            optionPicker("Reason", $vm.draft.reason, options.reasons)
            stringPicker("Category", $vm.draft.category, options.categories)
        }
        // Step 2 — outcome and tone
        Section("Outcome & tone") {
            stringPicker("Urgency", $vm.draft.urgency, options.urgencies)
            optionPicker("Outcome", $vm.draft.outcome, options.outcomes)
            optionPicker("Setting", $vm.draft.setting, options.settings)
            stringPicker("Tone", $vm.draft.tone, options.tones)
            stringPicker("Formality", $vm.draft.formality, options.formalities)
            stringPicker("Detail", $vm.draft.detailProfile, options.detailProfiles)
            stringPicker("Discretion", $vm.draft.discretionLevel, options.discretionLevels)
        }
        // Step 3 — continuity and follow-up
        Section("Continuity & follow-up") {
            optionPicker("Expected reply", $vm.draft.expectedResponse, options.expectedResponses)
            optionPicker("Follow-up", $vm.draft.followupBehavior, options.followupBehaviors)
            stringPicker("Continuity", $vm.draft.continuityScope, options.continuityScopes)
        }
        // Step 4 — optional context modules
        if !options.contextModules.isEmpty {
            Section("Use my profile context") {
                ForEach(options.contextModules, id: \.self) { module in
                    Toggle(module.capitalized, isOn: Binding(
                        get: { vm.draft.contextModules.contains(module) },
                        set: { on in
                            if on { vm.draft.contextModules.insert(module) }
                            else { vm.draft.contextModules.remove(module) }
                        }
                    ))
                }
            }
        }
        // Step 5 — channels
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
                stringPicker("Voice", $vm.draft.voiceStyle, options.voiceStyles)
                Stepper(
                    "Max length: \(vm.draft.callMaxSeconds)s",
                    value: $vm.draft.callMaxSeconds,
                    in: options.callSecondsMin...options.callSecondsMax,
                    step: 10
                )
            }
        }
        Section {
            Text("The wording is generated safely from your choices — you can't type custom call or text content. Enable a context module to weave in details from your Profile.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private func optionPicker(_ title: String, _ binding: Binding<String>, _ options: [TemplateOption]) -> some View {
        Picker(title, selection: binding) {
            ForEach(options) { Text($0.label).tag($0.code) }
        }
    }

    private func stringPicker(_ title: String, _ binding: Binding<String>, _ options: [String]) -> some View {
        Picker(title, selection: binding) {
            ForEach(options, id: \.self) { Text($0.replacingOccurrences(of: "_", with: " ").capitalized).tag($0) }
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
