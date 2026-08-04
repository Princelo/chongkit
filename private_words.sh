last_byte=$(tail -c 1 private.words.dict.encrypted | od -An -tx1 | tr -d ' \n')
if [[ "$last_byte" == "0a" ]]; then
    truncate -s -1 private.words.dict.encrypted
fi
python3 private_words.py $1 $2
