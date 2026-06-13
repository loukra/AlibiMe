import Foundation

/// Abstraction over the HTTP transport so tests can inject canned responses
/// without a live server. `URLSession` conforms in production.
public protocol HTTPTransport: Sendable {
    func send(_ request: URLRequest) async throws -> (Data, URLResponse)
}

extension URLSession: HTTPTransport {
    public func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        try await data(for: request)
    }
}

/// Supplies the current session token for authenticated requests.
public protocol TokenProviding: AnyObject, Sendable {
    var sessionToken: String? { get }
}

struct Endpoint {
    enum Method: String { case GET, POST, PATCH, PUT, DELETE }
    var method: Method
    var path: String
    var query: [URLQueryItem]
    var body: Data?
    var requiresAuth: Bool

    init(_ method: Method,
         _ path: String,
         query: [URLQueryItem] = [],
         body: Data? = nil,
         requiresAuth: Bool = true) {
        self.method = method
        self.path = path
        self.query = query
        self.body = body
        self.requiresAuth = requiresAuth
    }
}

/// The single owner of `URLSession` usage. Every service goes through this; no
/// other layer talks to the network directly.
public final class APIClient: @unchecked Sendable {
    private let baseURL: URL
    private let transport: HTTPTransport
    // Held strongly: the environment owns both the client and the token holder,
    // and the holder has no back-reference, so there is no retain cycle.
    private var tokenProvider: TokenProviding?

    public init(baseURL: URL,
                transport: HTTPTransport = URLSession.shared,
                tokenProvider: TokenProviding? = nil) {
        self.baseURL = baseURL
        self.transport = transport
        self.tokenProvider = tokenProvider
    }

    public func setTokenProvider(_ provider: TokenProviding) {
        self.tokenProvider = provider
    }

    func send<Response: Decodable>(_ endpoint: Endpoint, as type: Response.Type) async throws -> Response {
        let data = try await sendForData(endpoint)
        if data.isEmpty, let empty = EmptyResponse() as? Response {
            return empty
        }
        do {
            return try BCCoding.decoder.decode(Response.self, from: data)
        } catch {
            throw APIError.decoding(message: String(describing: error))
        }
    }

    func sendExpectingNoContent(_ endpoint: Endpoint) async throws {
        _ = try await sendForData(endpoint)
    }

    @discardableResult
    private func sendForData(_ endpoint: Endpoint) async throws -> Data {
        var components = URLComponents(url: baseURL.appendingPathComponent(endpoint.path),
                                       resolvingAgainstBaseURL: false)
        if !endpoint.query.isEmpty {
            components?.queryItems = endpoint.query
        }
        guard let url = components?.url else {
            throw APIError.transport(message: "Invalid URL for \(endpoint.path)")
        }

        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method.rawValue
        request.timeoutInterval = 30
        if let body = endpoint.body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if endpoint.requiresAuth, let token = tokenProvider?.sessionToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await transport.send(request)
        } catch {
            throw APIError.transport(message: error.localizedDescription)
        }

        guard let http = response as? HTTPURLResponse else {
            throw APIError.transport(message: "Non-HTTP response")
        }

        if (200..<300).contains(http.statusCode) {
            return data
        }
        throw Self.mapError(status: http.statusCode, data: data)
    }

    static func mapError(status: Int, data: Data) -> APIError {
        if let envelope = try? BCCoding.decoder.decode(ErrorResponseDTO.self, from: data) {
            let body = envelope.error
            switch body.code {
            case "unauthorized": return .unauthorized
            case "session_expired": return .sessionExpired
            default:
                return .api(code: body.code,
                            message: body.message,
                            retryable: body.retryable,
                            requestID: body.request_id)
            }
        }
        if status == 401 { return .unauthorized }
        return .unexpectedStatus(status)
    }
}

/// Marker used so endpoints with empty/ignored bodies can decode cleanly.
struct EmptyResponse: Decodable {}
