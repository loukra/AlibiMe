#if canImport(SwiftUI)
import SwiftUI

/// Settings: verified-number snapshot, profile, credits, help/legal, sign out.
public struct SettingsView: View {
    @Bindable var vm: SettingsViewModel
    private let locales = ["en", "de"]

    public init(vm: SettingsViewModel) { self.vm = vm }

    public var body: some View {
        NavigationStack {
            Form {
                Section("Your number") {
                    LabeledContent("Verified number", value: vm.maskedNumber ?? "—")
                }
                Section("Profile") {
                    TextField("Display name", text: $vm.displayName)
                    Picker("Language", selection: $vm.locale) {
                        ForEach(locales, id: \.self) { code in
                            Text(code == "de" ? "Deutsch" : "English").tag(code)
                        }
                    }
                    LabeledContent("Timezone", value: vm.timezone)
                    Button {
                        Task { await vm.save() }
                    } label: {
                        HStack {
                            Text("Save changes")
                            if vm.isSaving { Spacer(); ProgressView() }
                            else if vm.didSave { Spacer(); Image(systemName: "checkmark").foregroundStyle(Theme.success) }
                        }
                    }
                }
                Section("Plan") {
                    LabeledContent("Credits", value: "\(vm.creditsAvailable)")
                    LabeledContent("Plan", value: vm.planLabel)
                }
                if let error = vm.errorMessage {
                    Section { ErrorBanner(error) }
                }
                Section("About") {
                    Link("Help & support", destination: URL(string: "https://believablecall.example/help")!)
                    Link("Privacy & terms", destination: URL(string: "https://believablecall.example/legal")!)
                    LabeledContent("Version", value: vm.appVersion)
                }
                Section {
                    Button(role: .destructive) {
                        Task { await vm.signOut() }
                    } label: {
                        Text("Sign out")
                    }
                }
            }
            .navigationTitle("Settings")
            .task { await vm.load() }
        }
    }
}

struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsView(vm: SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService()))
    }
}
#endif
