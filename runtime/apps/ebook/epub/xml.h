#ifndef ER_EPUB_XML_H
#define ER_EPUB_XML_H
enum {EX_START=1,EX_END,EX_TEXT};
struct ex_attr {char key[64];const char*value;unsigned length;};
struct ex_tag {int kind,self;char name[64];const char*text;unsigned length,count;struct ex_attr attrs[32];};
struct ex_parser {const char*data;unsigned size,pos;int error;};
int ex_next(struct ex_parser*,struct ex_tag*);
int ex_attribute(const struct ex_tag*,const char*,char*,unsigned);
unsigned ex_decode(const char*,unsigned,char*,unsigned);
int ex_name(const char*,const char*);
#endif
