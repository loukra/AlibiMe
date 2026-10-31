#if canImport(SwiftUI)
import SwiftUI

/// A part of Settings another screen can open it at.
public enum SettingsFocus: Hashable {
    case number
    case credits
    /// The credits section with the Add Credits sheet already open.
    case addCredits
}

/// Settings: the account (number, name, language), credits, the Action
/// Button, help and legal, then sign out and delete. Changes save as they are
/// made; there is no Save button.
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
                    accountSection
                    creditsSection
                    quickAlibiSection
                    if let error = vm.errorMessage {
                        Section { ErrorBanner(error) }
                    }
                    Section {
                        Link("Help & support", destination: vm.supportURL)
                        Link("Privacy policy", destination: vm.privacyURL)
                        LabeledContent("Version", value: vm.appVersion)
                    } header: {
                        SectionHeader("About")
                    }
                    Section {
                        Button("Sign out") { Task { await vm.signOut() } }
                            .foregroundStyle(Theme.accent)
                        Button(role: .destructive) {
                            confirmingDelete = true
                        } label: {
                            HStack {
                                Text("Delete account")
                                if vm.isDeleting { Spacer(); ProgressView() }
                            }
                        }
                        .disabled(vm.isDeleting)
                        // On the button, so the confirmation points at it.
                        .confirmationDialog("Delete your account?", isPresented: $confirmingDelete, titleVisibility: .visible) {
                            Button("Delete account", role: .destructive) { Task { await vm.deleteAccount() } }
                            Button("Cancel", role: .cancel) {}
                        } message: {
                            Text("Your number, history, own alibis and remaining credits are deleted. Credits you bought are not refunded. This can't be undone.")
                        }
                    } footer: {
                        Text("Deleting removes your number, history, own alibis and any credits left.")
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
    var accountSection: some View {
        Section {
            LabeledContent("Number", value: vm.maskedNumber ?? "—")
                .id(SettingsFocus.number)
            Picker("Call language", selection: $vm.locale) {
                ForEach(locales, id: \.self) { code in
                    Text(code == "de" ? "Deutsch" : "English").tag(code)
                }
            }
            .onChange(of: vm.locale) { Task { await vm.saveIfChanged() } }
            LabeledContent("Timezone", value: AppLanguage.timeZoneName(vm.timezone))
        } header: {
            HStack {
                SectionHeader("Account")
                Spacer()
                if vm.isSaving {
                    ProgressView().controlSize(.mini)
                } else if vm.didSave {
                    Label("Saved", systemImage: "checkmark")
                        .labelStyle(.titleAndIcon)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.success)
                }
            }
        } footer: {
            Text("Calls and texts come to this number. They, and your alibis, use the language you pick here.")
        }
    }

    var creditsSection: some View {
        Section {
            LabeledContent("Credits available", value: "\(vm.creditsAvailable)")
            if let success = vm.creditSuccessMessage {
                Label(success, systemImage: "checkmark.circle.fill")
                    .font(.subheadline)
                    .foregroundStyle(Theme.success)
            }
            Button {
                creditPackagesVM = vm.makeCreditPackagesViewModel()
            } label: {
                Label("Add Credits", systemImage: "plus.circle.fill")
                    .font(.body.weight(.semibold))
                    .foregroundStyle(Theme.accent)
            }
        } header: {
            SectionHeader("Credits")
        } footer: {
            // The exact costs are configured on the backend and shown in the sheet.
            Text("A call uses more credits than a text. Add Credits shows how many.")
        }
        .id(SettingsFocus.credits)
    }

    var quickAlibiSection: some View {
        Section {
            Text("Press the Action Button and AlibiMe calls or texts you, without opening the app. Choose what it sends.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
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
            SectionHeader("Action Button")
        } footer: {
            Text("To set it up: iPhone Settings › Action Button › Shortcut › AlibiMe › Get Me Out. Siri and the Shortcuts app can run it too.")
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
