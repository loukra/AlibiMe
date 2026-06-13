import Foundation
import Observation

/// Drives the pre-auth flow: welcome → phone entry → OTP → done. The verified
/// number rule is reinforced in copy here; the user only ever enters their own
/// number for login.
@MainActor
@Observable
public final class AuthViewModel {
    public enum Step: Equatable {
        case welcome
        case phone
        case otp
        case done
    }

    public private(set) var step: Step = .welcome
    public var phoneNumber: String = ""
    public var code: String = ""
    public var locale: String = "en"
    public private(set) var isLoading = false
    public private(set) var errorMessage: String?
    public private(set) var verificationID: String?
    public private(set) var session: Session?
    /// Seconds until the user may request a new code. 0 means resend is allowed.
    public private(set) var resendCountdown: Int = 0

    private let auth: AuthServicing
    private let deviceID: String?
    /// Called once a session has been obtained.
    public var onAuthenticated: ((Session) -> Void)?

    public init(auth: AuthServicing, deviceID: String? = nil) {
        self.auth = auth
        self.deviceID = deviceID
    }

    public func begin() { step = .phone }

    /// Returns the flow to its start. Used when the auth screen reappears after
    /// sign-out / session expiry so the user doesn't land on a stale step.
    public func reset() {
        step = .welcome
        phoneNumber = ""
        code = ""
        verificationID = nil
        session = nil
        errorMessage = nil
        resendCountdown = 0
        isLoading = false
    }

    public var canSubmitPhone: Bool {
        !isLoading && AuthViewModel.normalizedPhone(phoneNumber) != nil
    }

    public var canSubmitCode: Bool {
        !isLoading && code.trimmingCharacters(in: .whitespaces).count >= 4
    }

    /// Strips formatting (spaces, parens, dashes) into a light E.164 candidate.
    /// The backend is authoritative for true validation.
    static func normalizedPhone(_ raw: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        let hasPlus = trimmed.hasPrefix("+")
        let digits = trimmed.filter(\.isNumber)
        guard digits.count >= 6 else { return nil }
        return hasPlus ? "+\(digits)" : digits
    }

    public func requestCode() async {
        guard let normalized = AuthViewModel.normalizedPhone(phoneNumber) else {
            errorMessage = "Enter your phone number including country code."
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let result = try await auth.start(phoneNumber: normalized, locale: locale, deviceID: deviceID)
            verificationID = result.verificationID
            step = .otp
            code = ""
            startResendCountdown()
        } catch {
            errorMessage = ErrorCopy.userMessage(for: asAPIError(error))
        }
    }

    public func confirmCode() async {
        guard let verificationID else {
            errorMessage = "Request a code first."
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let session = try await auth.confirm(verificationID: verificationID,
                                                 code: code.trimmingCharacters(in: .whitespaces),
                                                 deviceID: deviceID)
            self.session = session
            step = .done
            onAuthenticated?(session)
        } catch {
            errorMessage = ErrorCopy.userMessage(for: asAPIError(error))
        }
    }

    public func editPhoneNumber() {
        step = .phone
        verificationID = nil
        code = ""
        errorMessage = nil
    }

    public func resend() async {
        guard resendCountdown == 0 else { return }
        await requestCode()
    }

    /// Advances the resend countdown by one second; the view drives this with a
    /// timer. Kept here so behavior is unit-testable without real time.
    public func tick() {
        if resendCountdown > 0 { resendCountdown -= 1 }
    }

    private func startResendCountdown() { resendCountdown = 30 }
}
