/* SPDX-License-Identifier: GPL-3.0-or-later
 * Host-only fixtures around exact pinned RetroArch function excerpts.
 * The fake integer core is not an emulator or a game/save compatibility test.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

static int allocations, fail_at, live_allocations;
static void *test_malloc(size_t n) {
   void *p;
   if (++allocations == fail_at) return NULL;
   p = malloc(n); if (p) live_allocations++; return p;
}
static void *test_calloc(size_t n, size_t size) {
   void *p;
   if (++allocations == fail_at) return NULL;
   p = calloc(n, size); if (p) live_allocations++; return p;
}
static void test_free(void *p) { if (p) live_allocations--; free(p); }
#define malloc test_malloc
#define calloc test_calloc
#define free test_free

struct save_state_buf {void *data; size_t size; char path[128];};
struct sram_block {void *data; size_t size; unsigned type;};
struct list_item {union {unsigned i;} attr;};
struct string_list {size_t size; struct list_item *elems;};
typedef struct {unsigned id; size_t size; void *data;} retro_ctx_memory_info_t;
typedef struct {struct {bool block_sram_overwrite;} bools;} settings_t;
typedef struct {void *data; ssize_t size; uint8_t flags; char path[128];} load_task_data_t;
typedef struct {int unused;} retro_task_t;

#define SAVE_TASK_FLAG_LOAD_TO_BACKUP_BUFF 1
#define RARCH_LOG(...) ((void)0)
#define RARCH_ERR(...) (++errors)
static struct save_state_buf undo_load_buf, undo_save_buf;
static bool save_state_in_background;
static settings_t settings;
static struct list_item memory_item = {{0}};
static struct string_list memory_list = {1, &memory_item};
static int current_state, current_sram, errors, deserialize_calls, serialize_calls;
static bool serialize_failure, deserialize_failure, supported = true, zero_size;

static bool core_info_current_supports_savestate(void) {return supported;}
static void *savefile_ptr_get(void) {return settings.bools.block_sram_overwrite ? &memory_list : NULL;}
static settings_t *config_get_ptr(void) {return &settings;}
static void core_get_memory(retro_ctx_memory_info_t *info) {info->size=sizeof(current_sram);info->data=&current_sram;}
static size_t core_serialize_size(void) {return zero_size ? 0 : sizeof(current_state);}
static void *content_get_serialized_data(size_t *size) {
   int *p; serialize_calls++;
   if (serialize_failure) return NULL;
   p = malloc(sizeof(*p)); if (!p) return NULL;
   *p = current_state; *size = sizeof(*p); return p;
}
static bool content_deserialize_state(const void *p, size_t size) {
   deserialize_calls++;
   if (!p || size != sizeof(current_state)) return false;
   if (deserialize_failure) {current_state=-999;current_sram=-999;return false;}
   memcpy(&current_state,p,size);current_sram=current_state*100;return true;
}
static size_t fixture_strlcpy(char *dst, const char *src, size_t size) {
   size_t n=strlen(src);if(size){size_t count=n<size-1?n:size-1;memcpy(dst,src,count);dst[count]=0;}return n;
}
#ifdef strlcpy
#undef strlcpy
#endif
#define strlcpy fixture_strlcpy
static bool path_is_valid(const char *path) {(void)path;return false;}
static void task_push_load_and_save_state(const char *p,void *data,size_t size,bool a,bool b) {(void)p;(void)size;(void)a;(void)b;free(data);}
static void task_push_save_state(const char *p,void *data,size_t size,bool a) {(void)p;(void)size;(void)a;free(data);}
bool content_save_state(const char *path, bool save_to_disk);

/* PINNED_FUNCTIONS */

static void reset(void) {
   free(undo_load_buf.data);free(undo_save_buf.data);
   memset(&undo_load_buf,0,sizeof(undo_load_buf));memset(&undo_save_buf,0,sizeof(undo_save_buf));
   if(live_allocations){fprintf(stderr,"Fixture memory leaked\n");exit(2);}
   allocations=fail_at=errors=deserialize_calls=serialize_calls=0;
   current_state=100;current_sram=777;serialize_failure=deserialize_failure=zero_size=false;
   supported=true;save_state_in_background=false;settings.bools.block_sram_overwrite=false;
}
static void load(int value, bool backup_only) {
   load_task_data_t *request;int *bytes;int failure=fail_at;
   /* Inject allocation faults in the actual callback, not fixture construction. */
   fail_at=0;request=calloc(1,sizeof(*request));bytes=malloc(sizeof(*bytes));
   if(!request||!bytes)exit(2);
   *bytes=value;request->data=bytes;request->size=sizeof(*bytes);
   request->flags=backup_only?SAVE_TASK_FLAG_LOAD_TO_BACKUP_BUFF:0;
   strlcpy(request->path,"synthetic.state",sizeof(request->path));
   allocations=0;fail_at=failure;content_load_state_cb(NULL,request,NULL,NULL);
}
static void seed(int value) {
   current_state=value;if(!content_save_state("RAM",false))exit(2);
   allocations=0;serialize_calls=0;
}
#define REQUIRE(condition) do {if(!(condition)){fprintf(stderr,"FAIL %s line %d\n",name,__LINE__);return 1;}} while(0)
static int run(const char *name) {
   reset();
   if(!strcmp(name,"backup-failure")) {
      serialize_failure=true;load(20,false);
      REQUIRE(current_state==100 && deserialize_calls==0 && errors>0);
   } else if(!strcmp(name,"backup-allocation")) {
      fail_at=2;load(20,false);
      REQUIRE(current_state==100 && deserialize_calls==0 && errors>0);
   } else if(!strcmp(name,"older-undo-retained")) {
      seed(7);current_state=100;fail_at=2;load(20,false);
      REQUIRE(current_state==100 && deserialize_calls==0 && *(int*)undo_load_buf.data==7);
   } else if(!strcmp(name,"load-undo-redo")) {
      load(20,false);REQUIRE(current_state==20 && *(int*)undo_load_buf.data==100);
      REQUIRE(content_undo_load_state() && current_state==100);
      REQUIRE(content_undo_load_state() && current_state==20);
   } else if(!strcmp(name,"undo-backup-failure")) {
      seed(7);current_state=100;serialize_failure=true;
      REQUIRE(!content_undo_load_state() && current_state==100 && deserialize_calls==0 && *(int*)undo_load_buf.data==7);
   } else if(!strcmp(name,"undo-copy-allocation")) {
      seed(7);current_state=100;fail_at=1;
      REQUIRE(!content_undo_load_state() && current_state==100 && deserialize_calls==0 && *(int*)undo_load_buf.data==7);
   } else if(!strcmp(name,"undo-replacement-allocation")) {
      seed(7);current_state=100;fail_at=3;
      REQUIRE(!content_undo_load_state() && current_state==100 && deserialize_calls==0 && *(int*)undo_load_buf.data==7);
   } else if(!strcmp(name,"empty-undo")) {
      REQUIRE(!content_undo_load_state() && current_state==100 && deserialize_calls==0);
   } else if(!strcmp(name,"unsupported-core")) {
      supported=false;load(20,false);REQUIRE(current_state==100 && deserialize_calls==0);
   } else if(!strcmp(name,"failed-load-then-undo")) {
      deserialize_failure=true;load(20,false);REQUIRE(current_state==-999 && errors>0 && *(int*)undo_load_buf.data==100);
      deserialize_failure=false;REQUIRE(content_undo_load_state() && current_state==100);
   } else if(!strcmp(name,"sram-backup-failure")) {
      settings.bools.block_sram_overwrite=true;serialize_failure=true;load(20,false);
      REQUIRE(current_state==100 && current_sram==777 && deserialize_calls==0);
   } else if(!strcmp(name,"background-serialization")) {
      save_state_in_background=true;load(20,false);REQUIRE(current_state==20 && *(int*)undo_load_buf.data==100);
      REQUIRE(content_undo_load_state() && current_state==100);
   } else if(!strcmp(name,"backup-buffer-only")) {
      serialize_failure=true;load(20,true);
      REQUIRE(current_state==100 && deserialize_calls==0 && serialize_calls==0 && *(int*)undo_save_buf.data==20);
   } else if(!strcmp(name,"zero-serialization")) {
      zero_size=true;load(20,false);REQUIRE(current_state==100 && deserialize_calls==0);
   } else return 2;
   reset();printf("PASS %s\n",name);return 0;
}
int main(int argc,char **argv) {return argc==2?run(argv[1]):2;}
