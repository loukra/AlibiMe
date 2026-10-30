import Foundation

// Service protocols (consumed by view models) + their live implementations
// over `APIClient`. The rest of the app talks to these protocols, never to
// `APIClient` or `URLSession` directly. Mock implementations live in
// MockServices.swift for previews and unit tests.

public struct PhoneStartResult: Equatable, Sendable {
    public let verificationID: String
    public let channel: String
    public let expiresInSeconds: Int
    public init(verificationID: String, channel: String, expiresInSeconds: Int) {
        self.verificationID = verificationID
        self.channel = channel
        self.expiresInSeconds = expiresInSeconds
    }
}

public struct HistoryPage: Equatable, Sendable {
    public let items: [HistoryEntry]
    public let hasMore: Bool
    public let nextOffset: Int
    public init(items: [HistoryEntry], hasMore: Bool, nextOffset: Int) {
        self.items = items
        self.hasMore = hasMore
        self.nextOffset = nextOffset
    }
}

public protocol AuthServicing: Sendable {
    func start(phoneNumber: String, locale: String, deviceID: String?) async throws -> PhoneStartResult
    func confirm(verificationID: String, code: String, deviceID: String?) async throws -> Session
    func logout() async throws
}

public protocol TemplateServicing: Sendable {
    func list() async throws -> [TemplateSummary]
    /// Allowed structured choices for building a custom template.
    func options() async throws -> TemplateOptions
    /// Create a user-owned custom template from structured choices.
    func createCustom(_ draft: CustomTemplateDraft) async throws -> TemplateSummary
    /// Delete one of the user's own custom templates.
    func delete(id: String) async throws
}

public protocol RequestServicing: Sendable {
    func create(_ draft: RequestDraft) async throws -> RequestSummary
    func get(id: String) async throws -> RequestSummary
    func cancel(id: String) async throws -> RequestSummary
}

public protocol HistoryServicing: Sendable {
    func list(limit: Int, offset: Int) async throws -> HistoryPage
}

public protocol ProfileServicing: Sendable {
    func me() async throws -> UserProfile
    func update(locale: String?, timezone: String?, displayName: String?) async throws -> UserProfile
    /// Deletes the account and all its data on the backend.
    func deleteAccount() async throws
}

public protocol DeviceServicing: Sendable {
    func register(deviceID: String, pushToken: String?, appVersion: String?, osVersion: String?) async throws
}

public protocol CreditPackagesServicing: Sendable {
    /// The packs plus what a call and a text cost.
    func catalog() async throws -> CreditCatalog
    /// Acquire a package. `clientRequestID` makes the grant idempotent on the
    /// backend so repeated taps never double-grant.
    func acquire(code: String, clientRequestID: String) async throws -> CreditAcquisition
    /// Grant the credits of an App Store purchase (backend verifies it).
    func redeem(signedTransaction: String) async throws -> CreditAcquisition
}

public protocol ContextProfileServicing: Sendable {
    func get() async throws -> ContextProfile
    func update(_ profile: ContextProfile) async throws -> ContextProfile
}

/// Contacts authorization, normalized so view models don't depend on the
/// Contacts framework directly (and so it compiles on the macOS test host).
public enum ContactAuthorization: String, Sendable, Equatable {
    case notDetermined
    case authorized
    case limited
    case denied
    case restricted

    /// Whether we can present the prefilled new-contact sheet without first
    /// asking for permission.
    public var canPresentContactSheet: Bool {
        self == .authorized || self == .limited
    }
}

/// Permission gateway for the optional Save Contact flow. The prefilled
/// new-contact *sheet* itself is presented by the view layer (UIKit), so this
/// service only owns authorization — never contact creation without the user.
public protocol ContactsServicing: Sendable {
    func authorizationStatus() -> ContactAuthorization
    func requestAccess() async -> ContactAuthorization
}

// MARK: - Live implementations

public struct LiveAuthService: AuthServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func start(phoneNumber: String, locale: String, deviceID: String?) async throws -> PhoneStartResult {
        let body = try BCCoding.encoder.encode(
            PhoneStartRequestDTO(phone_number: phoneNumber, device_id: deviceID, locale: locale)
        )
        let dto = try await client.send(
            Endpoint(.POST, "v1/auth/phone/start", body: body, requiresAuth: false),
            as: PhoneStartResponseDTO.self
        )
        return PhoneStartResult(verificationID: dto.verification_id,
                                channel: dto.channel,
                                expiresInSeconds: dto.expires_in_seconds)
    }

    public func confirm(verificationID: String, code: String, deviceID: String?) async throws -> Session {
        let body = try BCCoding.encoder.encode(
            PhoneConfirmRequestDTO(verification_id: verificationID, code: code, device_id: deviceID)
        )
        let dto = try await client.send(
            Endpoint(.POST, "v1/auth/phone/confirm", body: body, requiresAuth: false),
            as: PhoneConfirmResponseDTO.self
        )
        return Session(token: dto.session_token,
                       userID: dto.user.id,
                       maskedNumber: dto.user.phone_number_masked)
    }

    public func logout() async throws {
        try await client.sendExpectingNoContent(Endpoint(.POST, "v1/auth/logout"))
    }
}

public struct LiveTemplateService: TemplateServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func list() async throws -> [TemplateSummary] {
        let dto = try await client.send(Endpoint(.GET, "v1/templates"), as: TemplateListResponseDTO.self)
        return dto.templates.map(TemplateSummary.init(dto:))
    }

    public func options() async throws -> TemplateOptions {
        let dto = try await client.send(
            Endpoint(.GET, "v1/templates/options"), as: TemplateOptionsResponseDTO.self
        )
        return TemplateOptions(dto: dto)
    }

    public func createCustom(_ draft: CustomTemplateDraft) async throws -> TemplateSummary {
        let body = try BCCoding.encoder.encode(
            CreateCustomTemplateBodyDTO(
                display_name: draft.displayName,
                description: draft.description.isEmpty ? nil : draft.description,
                category: draft.category,
                persona: draft.persona,
                reason: draft.reason,
                channels: draft.channels.map(\.wireValue),
                urgency: draft.urgency,
                outcome: draft.outcome,
                setting: draft.setting,
                tone: draft.tone,
                detail_profile: draft.detailProfile,
                discretion_level: draft.discretionLevel,
                formality: draft.formality,
                expected_response: draft.expectedResponse,
                followup_behavior: draft.followupBehavior,
                continuity_scope: draft.continuityScope,
                context_modules: Array(draft.contextModules),
                voice_style: draft.voiceStyle,
                call_max_seconds: draft.callMaxSeconds
            )
        )
        let dto = try await client.send(
            Endpoint(.POST, "v1/templates", body: body), as: TemplateOutDTO.self
        )
        return TemplateSummary(dto: dto)
    }

    public func delete(id: String) async throws {
        try await client.sendExpectingNoContent(Endpoint(.DELETE, "v1/templates/\(id)"))
    }
}

public struct LiveRequestService: RequestServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func create(_ draft: RequestDraft) async throws -> RequestSummary {
        let body = try BCCoding.encoder.encode(draft.toBody())
        let dto = try await client.send(
            Endpoint(.POST, "v1/requests", body: body),
            as: CreateRequestResponseDTO.self
        )
        return RequestSummary(dto: dto)
    }

    public func get(id: String) async throws -> RequestSummary {
        let dto = try await client.send(Endpoint(.GET, "v1/requests/\(id)"), as: RequestDetailDTO.self)
        return RequestSummary(dto: dto)
    }

    public func cancel(id: String) async throws -> RequestSummary {
        let dto = try await client.send(
            Endpoint(.POST, "v1/requests/\(id)/cancel"),
            as: CancelResponseDTO.self
        )
        // The cancel endpoint returns only id + status; re-fetch is unnecessary
        // for the UI, which just needs the new (terminal) status.
        return RequestSummary(
            id: dto.request_id,
            channel: .call,
            status: RequestStatus(wireValue: dto.status),
            scheduledKind: nil,
            executeAt: Date(),
            requestedAt: nil,
            cancelable: false,
            lastErrorCode: nil
        )
    }
}

public struct LiveHistoryService: HistoryServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func list(limit: Int, offset: Int) async throws -> HistoryPage {
        let dto = try await client.send(
            Endpoint(.GET, "v1/history", query: [
                URLQueryItem(name: "limit", value: String(limit)),
                URLQueryItem(name: "offset", value: String(offset)),
            ]),
            as: HistoryResponseDTO.self
        )
        return HistoryPage(
            items: dto.items.map(HistoryEntry.init(dto:)),
            hasMore: dto.has_more,
            nextOffset: dto.offset + dto.items.count
        )
    }
}

public struct LiveProfileService: ProfileServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func me() async throws -> UserProfile {
        let dto = try await client.send(Endpoint(.GET, "v1/me"), as: MeResponseDTO.self)
        return UserProfile(dto: dto)
    }

    public func update(locale: String?, timezone: String?, displayName: String?) async throws -> UserProfile {
        let body = try BCCoding.encoder.encode(
            MeUpdateDTO(locale: locale, timezone: timezone, display_name: displayName)
        )
        let dto = try await client.send(Endpoint(.PATCH, "v1/me", body: body), as: MeResponseDTO.self)
        return UserProfile(dto: dto)
    }

    public func deleteAccount() async throws {
        try await client.sendExpectingNoContent(Endpoint(.DELETE, "v1/me"))
    }
}

public struct LiveDeviceService: DeviceServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func register(deviceID: String, pushToken: String?, appVersion: String?, osVersion: String?) async throws {
        let body = try BCCoding.encoder.encode(
            DeviceUpsertDTO(device_id: deviceID, platform: "ios",
                            push_token: pushToken, app_version: appVersion, os_version: osVersion)
        )
        _ = try await client.send(Endpoint(.PUT, "v1/devices/current", body: body), as: DeviceResponseDTO.self)
    }
}

public struct LiveContextProfileService: ContextProfileServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func get() async throws -> ContextProfile {
        let dto = try await client.send(
            Endpoint(.GET, "v1/me/context-profile"), as: ContextProfileDTO.self
        )
        return ContextProfile(dto: dto)
    }

    public func update(_ profile: ContextProfile) async throws -> ContextProfile {
        let body = try BCCoding.encoder.encode(profile.toDTO())
        let dto = try await client.send(
            Endpoint(.PUT, "v1/me/context-profile", body: body), as: ContextProfileDTO.self
        )
        return ContextProfile(dto: dto)
    }
}

public struct LiveCreditPackagesService: CreditPackagesServicing {
    let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func catalog() async throws -> CreditCatalog {
        let dto = try await client.send(
            Endpoint(.GET, "v1/credit-packages"),
            as: CreditPackagesResponseDTO.self
        )
        return CreditCatalog(packages: dto.packages.map(CreditPackage.init(dto:)),
                             costs: dto.credit_costs.map { CreditCosts(call: $0.call, text: $0.sms) },
                             firstPurchaseBonus: dto.first_purchase_bonus ?? 0)
    }

    public func redeem(signedTransaction: String) async throws -> CreditAcquisition {
        let body = try BCCoding.encoder.encode(RedeemRequestDTO(signed_transaction: signedTransaction))
        let dto = try await client.send(
            Endpoint(.POST, "v1/credit-packages/redeem", body: body),
            as: AcquirePackageResponseDTO.self
        )
        return CreditAcquisition(dto: dto)
    }

    public func acquire(code: String, clientRequestID: String) async throws -> CreditAcquisition {
        let body = try BCCoding.encoder.encode(
            AcquirePackageRequestDTO(client_request_id: clientRequestID)
        )
        let dto = try await client.send(
            Endpoint(.POST, "v1/credit-packages/\(code)/acquire", body: body),
            as: AcquirePackageResponseDTO.self
        )
        return CreditAcquisition(dto: dto)
    }
}
