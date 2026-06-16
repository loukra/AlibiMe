import Foundation

/// A structured, backend-aware error. The networking layer always surfaces one
/// of these so the UI never has to parse `URLError` or raw status codes.
public enum APIError: Error, Equatable {
    /// A typed error returned by the backend error envelope.
    case api(code: String, message: String, retryable: Bool, requestID: String?)
    /// Authentication is required or the session is no longer valid.
    case unauthorized
    /// The session token expired and the user must sign in again.
    case sessionExpired
    /// The request never reached the server (offline, DNS, timeout, …).
    case transport(message: String)
    /// The response could not be decoded into the expected shape.
    case decoding(message: String)
    /// An unexpected HTTP status with no parseable envelope.
    case unexpectedStatus(Int)

    /// The backend error code, when one is available. Useful for routing logic
    /// (e.g. session expiry) without matching on copy.
    public var backendCode: String? {
        switch self {
        case let .api(code, _, _, _): return code
        case .unauthorized: return "unauthorized"
        case .sessionExpired: return "session_expired"
        default: return nil
        }
    }

    public var isRetryable: Bool {
        if case let .api(_, _, retryable, _) = self { return retryable }
        if case .transport = self { return true }
        return false
    }

    /// True when the user should be bounced back to the auth flow.
    public var requiresReauth: Bool {
        switch self {
        case .unauthorized, .sessionExpired:
            return true
        case let .api(code, _, _, _):
            return code == "unauthorized" || code == "session_expired"
        default:
            return false
        }
    }
}

/// Coerces any thrown error into an `APIError` so the UI mapping is uniform.
public func asAPIError(_ error: Error) -> APIError {
    if let api = error as? APIError { return api }
    return .transport(message: error.localizedDescription)
}

/// Maps backend error codes (and transport/decoding failures) to calm, neutral,
/// human copy. Raw backend codes never reach the UI.
public enum ErrorCopy {
    public static func userMessage(for error: APIError) -> String {
        switch error {
        case .unauthorized:
            return message(forCode: "unauthorized", fallback: nil)
        case .sessionExpired:
            return message(forCode: "session_expired", fallback: nil)
        case let .api(code, message, _, _):
            return self.message(forCode: code, fallback: message)
        case .transport:
            return "We couldn’t reach the network. Check your connection and try again."
        case .decoding:
            return "Something went wrong. Please try again."
        case .unexpectedStatus:
            return "Something went wrong. Please try again."
        }
    }

    /// Human copy keyed by the backend's documented error codes.
    private static func message(forCode code: String, fallback: String?) -> String {
        switch code {
        case "unauthorized":
            return "Please sign in to continue."
        case "session_expired":
            return "Your session has expired. Please sign in again."
        case "phone_not_verified":
            return "Verify your phone number before sending a request."
        case "invalid_phone_number":
            return "That phone number doesn’t look right. Please check it and try again."
        case "unsupported_line_type":
            return "We can’t use this type of phone line. Try a mobile number."
        case "rate_limited":
            return "You’re going a little fast. Please wait a moment and try again."
        case "active_request_exists":
            return "You’ve reached the limit of queued jobs. Cancel one to schedule another."
        case "template_channel_not_supported":
            return "This template can’t be sent on that channel."
        case "insufficient_credits":
            return "You’re out of credits. Add more to keep sending."
        case "invalid_schedule_window":
            return "Pick a time within the next 24 hours."
        case "request_not_cancelable":
            return "This request can no longer be canceled."
        case "provider_unavailable":
            return "The service is briefly unavailable. Please try again shortly."
        case "validation_failed":
            return "Some details weren’t accepted. Please review and try again."
        case "not_found":
            return "We couldn’t find that. Please try again."
        default:
            // Never leak a raw backend code; prefer a clean generic line.
            return fallback?.isEmpty == false ? "Something went wrong. Please try again." : "Something went wrong. Please try again."
        }
    }
}
