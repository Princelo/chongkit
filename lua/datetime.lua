-- lua/datetime.lua
local function translator(input, seg)
    if input == "/time" then
        yield(Candidate("time", seg.start, seg._end, os.date("%H:%M"), " 時間"))
        yield(Candidate("time", seg.start, seg._end, os.date("%H:%M:%S"), " 時分秒"))
    elseif input == "/datetime" then
        yield(Candidate("datetime", seg.start, seg._end, os.date("%Y-%m-%d %H:%M:%S"), " 日期時間"))
    elseif input == "/date" then
        yield(Candidate("date", seg.start, seg._end, os.date("%Y-%m-%d"), " 日期"))
        yield(Candidate("date", seg.start, seg._end, os.date("%Y年%m月%d日"), " 中文日期"))
    elseif input == "/ts" then
        yield(Candidate("ts", seg.start, seg._end, tostring(os.time()), " Timestamp"))
        yield(Candidate("ts", seg.start, seg._end, tostring(os.time() * 1000), " Timestamp"))
    end
end
return translator
