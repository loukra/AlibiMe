#if canImport(SwiftUI)
import SwiftUI

/// A part of Settings another screen can open it at.
public enum SettingsFocus: Hashable {
    case number
    case credits
    /// The credits section with the Add Credits sheet already open.
    case addCredits
}

/// Settings: verified-number snapshot, profile, credits, help/legal, sign out.
public struct SettingsView: View {
    @Bindable var vm: SettingsViewModel
    /// Non-nil while the Add Credits sheet is open (`.sheet(item:)`, so the
    /// sheet never renders before the view model exists).
    @State private var creditPackagesVM: CreditPackagesViewModel?
    @State private var confirmingDelete = false
    /// Set from outside (Home's pills); scrolled to once, then cleared.
    @Binding private var focus: SettingsFocus?
    private let locales = ["en", "de"]

    public init(vm: SettingsViewModel, focus: Binding<SettingsFocus?> = .constant(nil)) {
        self.vm = vm
        self._focus = focus
    }

    public var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                Form {
                    Section("Your number") {
                        LabeledContent("Verified number", value: vm.maskedNumber ?? "—")
                    }
                    .id(SettingsFocus.number)
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
                        LabeledContent("Plan tier", value: vm.planLabel)
                    }
                    Section {
                        Button {
                            creditPackagesVM = vm.makeCreditPackagesViewModel()
                        } label: {
                            Label("Add Credits", systemImage: "plus.circle.fill")
                                .font(.body.weight(.semibold))
                                .foregroundStyle(Theme.accent)
                        }
                        if let success = vm.creditSuccessMessage {
                            Label(success, systemImage: "checkmark.circle.fill")
                                .font(.subheadline)
                                .foregroundStyle(Theme.success)
                        }
                        LabeledContent("Credits available", value: "\(vm.creditsAvailable)")
                    } footer: {
                        Text("Credits are used each time you request a call or text.")
                    }
                    .id(SettingsFocus.credits)
                    quickAlibiSection
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
                    Section {
                        Button(role: .destructive) {
                            confirmingDelete = true
                        } label: {
                            HStack {
                                Text("Delete account")
                                if vm.isDeleting { Spacer(); ProgressView() }
                            }
                        }
                        .disabled(vm.isDeleting)
                    } footer: {
                        Text("Deletes your number, history, custom templates and any credits left.")
                    }
                }
                .onChange(of: focus) { _, target in
                    guard let target else { return }
                    withAnimation {
                        proxy.scrollTo(target == .number ? SettingsFocus.number : .credits, anchor: .top)
                    }
                    if target == .addCredits {
                        creditPackagesVM = vm.makeCreditPackagesViewModel()
                    }
                    focus = nil
                }
            }
            .bcClearScrollBackground()
            .bcTabBarClearance()
            .bcScreenBackground()
            .navigationTitle("Settings")
            .task { await vm.load() }
            .confirmationDialog("Delete your account?", isPresented: $confirmingDelete, titleVisibility: .visible) {
                Button("Delete account", role: .destructive) { Task { await vm.deleteAccount() } }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Your number, history, custom templates and remaining credits are deleted. Credits you bought are not refunded. This can't be undone.")
            }
            .sheet(item: $creditPackagesVM) { packagesVM in
                AddCreditsSheet(
                    vm: packagesVM,
                    onClose: { creditPackagesVM = nil },
                    onAcquired: { result in
                        creditPackagesVM = nil
                        Task { await vm.didAcquireCredits(result) }
                    }
                )
                .bcSheetDetents()
            }
        }
    }
}

private extension SettingsView {
    var quickAlibiSection: some View {
        Section {
            Picker("Alibi", selection: Binding(
                get: { vm.quickAlibi?.templateID ?? "" },
                set: { vm.setQuickAlibi(templateID: $0.isEmpty ? nil : $0) }
            )) {
                Text("Off").tag("")
                ForEach(vm.quickAlibiTemplates) { template in
                    Text(template.displayName).tag(template.id)
                }
            }
            if let alibi = vm.quickAlibi {
                if vm.quickAlibiChannels.count > 1 {
                    Picker("Send as", selection: Binding(
                        get: { alibi.channel },
                        set: { vm.setQuickAlibiChannel($0) }
                    )) {
                        Text("Call").tag(Channel.call)
                        Text("Text").tag(Channel.text)
                    }
                    .pickerStyle(.segmented)
                }
                Picker("When", selection: Binding(
                    get: { alibi.timing.delaySeconds ?? 0 },
                    set: { vm.setQuickAlibiDelay($0) }
                )) {
                    ForEach(TimingOption.presets) { option in
                        Text(option.shortTitle).tag(option.delaySeconds ?? 0)
                    }
                }
            }
        } header: {
            Text("Action Button")
        } footer: {
            Text("In the iPhone Settings under Action Button, choose Shortcut and pick AlibiMe's \"Get Me Out\". Siri and the Shortcuts app can run it too.")
        }
    }
}

struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsView(vm: SettingsViewModel(profileService: MockProfileService(),
                                           auth: MockAuthService(),
                                           creditPackages: MockCreditPackagesService()))
    }
}
#endif
