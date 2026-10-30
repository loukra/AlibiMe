#if canImport(SwiftUI)
import SwiftUI

/// The Profile tab: optional, reusable life-context the composer can use to make
/// custom templates more believable. Nothing here is required. Every field is
/// asked as a plain question, and each section says what the caller does with it.
public struct ProfileView: View {
    @Bindable var vm: ProfileViewModel
    @State private var confirmClear = false

    public init(vm: ProfileViewModel) { self.vm = vm }

    public var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: Spacing.s) {
                        Label("Make your calls sound like your life", systemImage: "person.text.rectangle")
                            .font(.headline)
                        Text("When you write your own call, the caller can mention your job, your home or your family, so the reason sounds like it's really about you. Everything is optional, and you can clear it anytime.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.vertical, Spacing.xs)
                }

                Section {
                    picker("What field do you work in?", \.workIndustry, vm.options.workIndustries)
                    picker("What's your position?", \.workRoleLevel, vm.options.workRoleLevels)
                    picker("Where do you work?", \.workSetting, vm.options.workSettings)
                    picker("When do you work?", \.workSchedule, vm.options.workSchedules)
                    picker("Do you travel for work?", \.workTravelScope, vm.options.workTravelScopes)
                } header: {
                    Text("Work")
                } footer: {
                    Text("So a caller can say your shift moved or a client needs you.")
                }

                Section {
                    picker("Who do you live with?", \.livingSetup, vm.options.livingSetups)
                    multiSelect("What do you look after?", \.homeResponsibilities, vm.options.homeResponsibilities)
                    multiSelect("Who depends on you?", \.dependentContexts, vm.options.dependentContexts)
                } header: {
                    Text("Home")
                } footer: {
                    Text("For reasons like the landlord coming by or the dog sitter canceling.")
                }

                Section {
                    picker("Do you help your family?", \.familySupportLevel, vm.options.familySupportLevels)
                    picker("Where do they live?", \.familyProximity, vm.options.familyProximities)
                } header: {
                    Text("Family")
                } footer: {
                    Text("For a relative who suddenly needs you.")
                }

                Section {
                    picker("Who knows you're together?", \.relationshipVisibility, vm.options.relationshipVisibilities)
                    picker("How long together?", \.relationshipStage, vm.options.relationshipStages)
                } header: {
                    Text("Partner")
                } footer: {
                    Text("Tells the caller whether mentioning your partner is fine.")
                }

                Section {
                    picker("Anything new in your life?", \.transitionState, vm.options.transitionStates)
                    picker("For how long?", \.transitionHorizon, vm.options.transitionHorizons)
                } header: {
                    Text("Recent changes")
                } footer: {
                    Text("Something new, like a job or a move, makes a sudden call easy to believe.")
                }

                Section {
                    picker("How much detail?", \.privacyPreference, vm.options.privacyPreferences)
                } header: {
                    Text("Details")
                } footer: {
                    Text("With \"Keep it vague\" the caller sticks to general reasons.")
                }

                if let error = vm.errorMessage {
                    Section { ErrorBanner(error) }
                }

                Section {
                    Button(role: .destructive) {
                        confirmClear = true
                    } label: { Text("Clear my answers") }
                }
            }
            .bcClearScrollBackground()
            .bcTabBarClearance()
            .bcScreenBackground()
            .navigationTitle("Profile")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    if vm.isSaving {
                        ProgressView()
                    } else if vm.hasChanges {
                        Button("Save") { Task { await vm.save() } }
                    } else if vm.didSave {
                        Label("Saved", systemImage: "checkmark")
                            .labelStyle(.titleAndIcon)
                            .foregroundStyle(Theme.success)
                    }
                }
            }
            .confirmationDialog("Clear all your answers?", isPresented: $confirmClear, titleVisibility: .visible) {
                Button("Clear", role: .destructive) { Task { await vm.clearAll() } }
            } message: {
                Text("Your calls will still work, they just won't mention your life.")
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
            Text("Skip").tag("")
            ForEach(options) { Text($0.label).tag($0.code) }
        }
    }

    // Multi-select rendered as a disclosure of toggles; the row shows how many
    // are picked so the answer is visible without opening it.
    private func multiSelect(
        _ title: String,
        _ keyPath: WritableKeyPath<ContextProfile, [String]>,
        _ options: [TemplateOption]
    ) -> some View {
        DisclosureGroup {
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
        } label: {
            HStack {
                Text(title)
                Spacer()
                let picked = options.filter { vm.profile[keyPath: keyPath].contains($0.code) }
                Text(picked.isEmpty ? "Skip" : picked.map(\.label).joined(separator: ", "))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
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
