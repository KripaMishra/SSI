text data cleaning steps (to be written in Scripts/clean_docs.py):
0. Primary task is name/contactNum/email redaction, whitespace cleaning, metadata extraction. start with writing tests and then the scripts. finally run on Data/docs and output to be saved in cleaned/
1. Extract the category of the text reference such as: Operations Note, Internal Note, Internal Email - Supply, vs Internal Email - Demand Planning etc. 
2. attributes after PII redaction, for mails: FROM <REDACTED_NAME> <REDACTED_EMAIL> actual message. 
3. Keep one chunk per note, no overlap while chunking, text is small enough to keep it simple 
4. Create detailed redaction pipline preprocessor for names, contact, valid Emails.
5. Tags such as """suggests a lapsed promo caused the decline (false) _Note: attribution unverified._
""" in /home/kripa/Personal/projects/SSI/Data/docs/promo_note_redherring_02b.txt
6. Tags such as SOP:
7. PII redaction: Final response saves a metadata from the run as how many redactions done, and count per category.
8. Don't remove the filler words, text already concise and might loose contextual information.
9. clean for empty new lines
10. just write the tests. and the preprocessing scipt, the output to be stored stored in a jsonl file with id, text(cleaned text), metadata{extracted tags etc}.
-----
Done Oneshot
