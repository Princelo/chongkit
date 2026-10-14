-- lua/uuid.lua
local function random_hex(n)
    local hex_chars = "0123456789abcdef"
    local parts = {}
    for _ = 1, n do
        local i = math.random(1, 16)
        table.insert(parts, hex_chars:sub(i, i))
    end
    return table.concat(parts)
end

local function gen_uuid_v4()
    local y_candidates = {"8", "9", "a", "b"}
    local y = y_candidates[math.random(1, 4)]

    return string.format("%s-%s-4%s-%s%s-%s",
        random_hex(8),
        random_hex(4),
        random_hex(3),
        y,
        random_hex(3),
        random_hex(12)
    )
end

local function translator(input, seg)
    if input == "/uuid" then
        local lower = gen_uuid_v4()
        local upper = string.upper(lower)
        local lower_no_dash = string.gsub(lower, "-", "")
        local upper_no_dash = string.gsub(upper, "-", "")

        yield(Candidate("uuid", seg.start, seg._end, lower, " uuid‑v4"))
        yield(Candidate("uuid", seg.start, seg._end, upper, " UUID‑V4"))
        yield(Candidate("uuid", seg.start, seg._end, lower_no_dash, " uuid‑v4 without hyphens"))
        yield(Candidate("uuid", seg.start, seg._end, upper_no_dash, " UUID‑V4 without hyphens"))
    end
end

return translator
