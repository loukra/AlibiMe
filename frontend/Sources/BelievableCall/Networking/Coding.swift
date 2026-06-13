import Foundation

/// JSON coders configured to match the backend's wire format.
///
/// The backend emits ISO-8601 timestamps with a trailing `Z`, sometimes with
/// fractional seconds (e.g. `2026-06-13T14:37:59.855827Z`) and sometimes
/// without. Foundation's built-in `.iso8601` strategy rejects fractional
/// seconds, so we parse both forms explicitly.
enum BCCoding {
    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let raw = try container.decode(String.self)
            if let date = parseDate(raw) {
                return date
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Unrecognized date format: \(raw)"
            )
        }
        return d
    }()

    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .custom { date, encoder in
            var container = encoder.singleValueContainer()
            try container.encode(isoString(from: date))
        }
        return e
    }()

    private static let withFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let withoutFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func parseDate(_ raw: String) -> Date? {
        withFractional.date(from: raw) ?? withoutFractional.date(from: raw)
    }

    /// Encodes a date as an internet date-time string with a `Z` suffix, which
    /// the backend accepts for `scheduled_at` (it requires a tz offset).
    static func isoString(from date: Date) -> String {
        withFractional.string(from: date)
    }
}
