#if canImport(SwiftUI)
import SwiftUI

/// Pre-auth flow container: welcome → phone → OTP. On `.done` the parent swaps
/// to the main app.
public struct AuthFlowView: View {
    @Bindable var vm: AuthViewModel
    var sessionExpiredNotice: Bool

    public init(vm: AuthViewModel, sessionExpiredNotice: Bool = false) {
        self.vm = vm
        self.sessionExpiredNotice = sessionExpiredNotice
    }

    public var body: some View {
        ZStack {
            Theme.backgroundGradient.ignoresSafeArea()
            switch vm.step {
            case .welcome:
                WelcomeView(sessionExpiredNotice: sessionExpiredNotice) { vm.begin() }
            case .phone:
                PhoneEntryView(vm: vm)
            case .otp:
                OTPView(vm: vm)
            case .done:
                ProgressView()
            }
        }
        .animation(.easeInOut(duration: 0.2), value: vm.step)
    }
}

struct WelcomeView: View {
    var sessionExpiredNotice: Bool
    let onContinue: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.l) {
            Spacer()
            // Same logo as LaunchView, so launch flows straight into welcome.
            VStack(spacing: Spacing.xs) {
                Image("LaunchLogo", bundle: .module)
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: 180, maxHeight: 180)
                    .accessibilityLabel("AlibiMe")
                Text("Get a call or text when you need a reason to leave.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            if sessionExpiredNotice {
                ErrorBanner(String(localized: "Your session expired. Please sign in again."))
            }
            Spacer()
            VStack(spacing: Spacing.s) {
                PrimaryButton("Get started", action: onContinue)
                Text("We only ever contact your own verified number.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
            }
        }
        .padding(Spacing.l)
    }
}

struct PhoneEntryView: View {
    @Bindable var vm: AuthViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.l) {
            VStack(alignment: .leading, spacing: Spacing.s) {
                Text("Your phone number")
                    .font(.title2.bold())
                Text("We’ll send a verification code. The app only ever contacts this verified number.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Card {
                HStack(spacing: Spacing.m) {
                    Menu {
                        Picker("Country", selection: $vm.country) {
                            ForEach(PhoneCountry.all) { country in
                                Text("\(country.flag) \(country.name) +\(country.dialCode)").tag(country)
                            }
                        }
                    } label: {
                        HStack(spacing: Spacing.xs) {
                            Text("\(vm.country.flag) +\(vm.country.dialCode)")
                                .monospacedDigit()
                            Image(systemName: "chevron.down")
                                .font(.caption.weight(.semibold))
                        }
                        .font(.title3)
                    }
                    .tint(.primary)
                    .accessibilityLabel("Country code +\(vm.country.dialCode), \(vm.country.name)")
                    Divider().frame(height: 28)
                    TextField("151 23456789", text: $vm.phoneNumber)
                        .font(.title3)
                        .bcPhoneKeyboard()
                        .onChange(of: vm.phoneNumber) { vm.phoneNumberChanged() }
                }
            }
            if let error = vm.errorMessage {
                ErrorBanner(error)
            }
            Spacer()
            PrimaryButton("Send code", isLoading: vm.isLoading) {
                Haptics.play(.impact)
                Task { await vm.requestCode() }
            }
            .disabled(!vm.canSubmitPhone)
            .opacity(vm.canSubmitPhone ? 1 : 0.5)
        }
        .padding(Spacing.l)
    }
}

struct OTPView: View {
    @Bindable var vm: AuthViewModel
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.l) {
            VStack(alignment: .leading, spacing: Spacing.s) {
                Text("Enter the code")
                    .font(.title2.bold())
                Text("We sent a 6-digit code to \(vm.fullNumber ?? vm.phoneNumber).")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Button("Use a different number") { vm.editPhoneNumber() }
                    .font(.subheadline)
                    .foregroundStyle(Theme.accent)
            }
            Card {
                TextField("123456", text: $vm.code)
                    .font(.system(.title, design: .monospaced))
                    .bcNumberKeyboard()
            }
            if let error = vm.errorMessage {
                ErrorBanner(error)
            }
            HStack {
                if vm.resendCountdown > 0 {
                    Text("Resend code in \(vm.resendCountdown)s")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                } else {
                    Button("Resend code") { Task { await vm.resend() } }
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(Theme.accent)
                }
            }
            Spacer()
            PrimaryButton("Verify", isLoading: vm.isLoading) {
                Haptics.play(.impact)
                Task { await vm.confirmCode() }
            }
            .disabled(!vm.canSubmitCode)
            .opacity(vm.canSubmitCode ? 1 : 0.5)
        }
        .padding(Spacing.l)
        .onReceive(timer) { _ in vm.tick() }
    }
}

struct AuthFlowView_Previews: PreviewProvider {
    static var previews: some View {
        AuthFlowView(vm: AuthViewModel(auth: MockAuthService()))
    }
}
#endif
