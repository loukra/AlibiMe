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
            Theme.background.ignoresSafeArea()
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
            VStack(alignment: .leading, spacing: Spacing.m) {
                Image(systemName: "phone.badge.waveform.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(Theme.accent)
                Text("BelievableCall")
                    .font(.largeTitle.bold())
                Text("Receive a believable call or text to your own number. Choose a template and timing — for work, family, social, logistics, or safety reasons.")
                    .font(.body)
                    .foregroundStyle(.secondary)
            }
            if sessionExpiredNotice {
                ErrorBanner("Your session expired. Please sign in again.")
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
                TextField("+1 555 123 4567", text: $vm.phoneNumber)
                    .font(.title3)
                    .bcPhoneKeyboard()
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
                Text("We sent a 6-digit code to \(vm.phoneNumber).")
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
