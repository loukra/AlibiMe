#if canImport(SwiftUI)
import SwiftUI

/// The Profile tab: optional, reusable life-context the composer can use to make
/// custom templates more believable. Nothing here is required.
public struct ProfileView: View {
    @Bindable var vm: ProfileViewModel

    public init(vm: ProfileViewModel) { self.vm = vm }

    public var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Optional. Add as much or as little as you like — it only makes your custom templates more believable, and you can clear it anytime.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Work") {
                    picker("Industry", \.workIndustry, vm.options.workIndustries)
                    picker("Role", \.workRoleLevel, vm.options.workRoleLevels)
                    picker("Setting", \.workSetting, vm.options.workSettings)
                    picker("Schedule", \.workSchedule, vm.options.workSchedules)
                    picker("Travel", \.workTravelScope, vm.options.workTravelScopes)
                }

                Section("Home") {
                    picker("Living setup", \.livingSetup, vm.options.livingSetups)
                    multiSelect("Responsibilities", \.homeResponsibilities, vm.options.homeResponsibilities)
                    multiSelect("Dependents", \.dependentContexts, vm.options.dependentContexts)
                }

                Section("Family & care") {
                    picker("Support level", \.familySupportLevel, vm.options.familySupportLevels)
                    picker("Proximity", \.familyProximity, vm.options.familyProximities)
                }

                Section("Relationship & privacy") {
                    picker("Visibility", \.relationshipVisibility, vm.options.relationshipVisibilities)
                    picker("Stage", \.relationshipStage, vm.options.relationshipStages)
                    picker("Privacy", \.privacyPreference, vm.options.privacyPreferences)
                }

                Section("Transition") {
                    picker("Situation", \.transitionState, vm.options.transitionStates)
                    picker("Horizon", \.transitionHorizon, vm.options.transitionHorizons)
                }

                if let error = vm.errorMessage {
                    Section { ErrorBanner(error) }
                }

                Section {
                    Button(role: .destructive) {
                        Task { await vm.clearAll() }
                    } label: { Text("Clear all context") }
                }
            }
            .bcClearScrollBackground()
            .bcScreenBackground()
            .navigationTitle("Profile")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    if vm.isSaving {
                        ProgressView()
                    } else {
                        Button("Save") { Task { await vm.save() } }
                    }
                }
            }
            .task { if vm.phase == .idle { await vm.load() } }
        }
    }

    // Optional single-choice picker bound to a String? ("" == not set).
    private func picker(
        _ title: String,
        _ keyPath: WritableKeyPath<ContextProfile, String?>,
        _ options: [TemplateOption]
    ) -> some View {
        let binding = Binding(
            get: { vm.profile[keyPath: keyPath] ?? "" },
            set: { vm.profile[keyPath: keyPath] = $0.isEmpty ? nil : $0 }
        )
        return Picker(title, selection: binding) {
            Text("Not set").tag("")
            ForEach(options) { Text($0.label).tag($0.code) }
        }
    }

    // Multi-select rendered as a disclosure of toggles.
    private func multiSelect(
        _ title: String,
        _ keyPath: WritableKeyPath<ContextProfile, [String]>,
        _ options: [TemplateOption]
    ) -> some View {
        DisclosureGroup(title) {
            ForEach(options) { option in
                let isOn = Binding(
                    get: { vm.profile[keyPath: keyPath].contains(option.code) },
                    set: { on in
                        var set = vm.profile[keyPath: keyPath]
                        if on { if !set.contains(option.code) { set.append(option.code) } }
                        else { set.removeAll { $0 == option.code } }
                        vm.profile[keyPath: keyPath] = set
                    }
                )
                Toggle(option.label, isOn: isOn)
            }
        }
    }
}

struct ProfileView_Previews: PreviewProvider {
    static var previews: some View {
        ProfileView(vm: ProfileViewModel(service: MockContextProfileService(),
                                         templates: MockTemplateService()))
    }
}
#endif
