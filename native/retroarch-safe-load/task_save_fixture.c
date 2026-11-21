/*  RetroArch - A frontend for libretro.
 *  Copyright (C) 2011-2017 - Daniel De Matteis
 *  Copyright (C) 2016-2019 - Brad Parker
 *
 *  RetroArch is free software: you can redistribute it and/or modify it under the terms
 *  of the GNU General Public License as published by the Free Software Found-
 *  ation, either version 3 of the License, or (at your option) any later version.
 *
 *  RetroArch is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 *  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 *  PURPOSE.  See the GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License along with RetroArch.
 *  If not, see <http://www.gnu.org/licenses/>.
 */
/* Exact function excerpts from the pinned tasks/task_save.c; host fixtures only. */

bool content_undo_load_state(void)
{
   unsigned i;
   size_t temp_data_size;
   bool ret                  = false;
   unsigned num_blocks       = 0;
   void *temp_data           = NULL;
   struct sram_block *blocks = NULL;
   struct string_list *savefile_list = (struct string_list*)savefile_ptr_get();

   if (!core_info_current_supports_savestate())
   {
      RARCH_LOG("[State] %s\n",
            msg_hash_to_str(MSG_CORE_DOES_NOT_SUPPORT_SAVESTATES));
      return false;
   }

   RARCH_LOG("[State] %s \"%s\", %u %s.\n",
         msg_hash_to_str(MSG_LOADING_STATE),
         undo_load_buf.path,
         (unsigned)undo_load_buf.size,
         msg_hash_to_str(MSG_BYTES));

   /* TODO/FIXME - This checking of SRAM overwrite,
    * the backing up of it and
    * its flushing could all be in their
    * own functions... */
   if (     savefile_list
         && savefile_list->size
         && config_get_ptr()->bools.block_sram_overwrite)
   {
      RARCH_LOG("[SRAM] %s.\n",
            msg_hash_to_str(MSG_BLOCKING_SRAM_OVERWRITE));

      if ((blocks = (struct sram_block*)
         calloc(savefile_list->size, sizeof(*blocks))))
      {
         num_blocks = (unsigned)savefile_list->size;
         for (i = 0; i < num_blocks; i++)
            blocks[i].type = savefile_list->elems[i].attr.i;
      }
   }

   for (i = 0; i < num_blocks; i++)
   {
      retro_ctx_memory_info_t    mem_info;

      mem_info.id = blocks[i].type;
      core_get_memory(&mem_info);

      blocks[i].size = mem_info.size;
   }

   for (i = 0; i < num_blocks; i++)
      if (blocks[i].size)
         blocks[i].data = malloc(blocks[i].size);

   /* Backup current SRAM which is overwritten by unserialize. */
   for (i = 0; i < num_blocks; i++)
   {
      if (blocks[i].data)
      {
         retro_ctx_memory_info_t    mem_info;
         const void *ptr = NULL;

         mem_info.id = blocks[i].type;

         core_get_memory(&mem_info);

         if ((ptr = mem_info.data))
            memcpy(blocks[i].data, ptr, blocks[i].size);
      }
   }

   /* We need to make a temporary copy of the buffer, to allow the swap below */
   temp_data              = malloc(undo_load_buf.size);
   temp_data_size         = undo_load_buf.size;
   memcpy(temp_data, undo_load_buf.data, undo_load_buf.size);

   /* Swap the current state with the backup state. This way, we can undo
   what we're undoing */
   content_save_state("RAM", false);

   ret = content_deserialize_state(temp_data, temp_data_size);

   /* Clean up the temporary copy */
   free(temp_data);
   temp_data              = NULL;

    /* Flush back. */
   for (i = 0; i < num_blocks; i++)
   {
      if (blocks[i].data)
      {
         retro_ctx_memory_info_t    mem_info;
         void *ptr   = NULL;

         mem_info.id = blocks[i].type;

         core_get_memory(&mem_info);

         if ((ptr = mem_info.data))
            memcpy(ptr, blocks[i].data, blocks[i].size);
      }
   }

   for (i = 0; i < num_blocks; i++)
   {
      free(blocks[i].data);
      blocks[i].data = NULL;
   }
   free(blocks);

   if (!ret)
   {
      RARCH_ERR("[State] %s \"%s\".\n",
         msg_hash_to_str(MSG_FAILED_TO_UNDO_LOAD_STATE),
         undo_load_buf.path);
      return false;
   }

   return true;
}

static void content_load_state_cb(retro_task_t *task,
      void *task_data,
      void *user_data, const char *error)
{
   unsigned i;
   bool ret;
   load_task_data_t *load_data = (load_task_data_t*)task_data;
   ssize_t _len                = load_data->size;
   unsigned num_blocks         = 0;
   void *buf                   = load_data->data;
   struct sram_block *blocks   = NULL;
   struct string_list *savefile_list = (struct string_list*)savefile_ptr_get();

#ifdef HAVE_CHEEVOS
   if (rcheevos_hardcore_active())
      goto error;
#endif

   RARCH_LOG("[State] %s \"%s\", %u %s.\n",
         msg_hash_to_str(MSG_LOADING_STATE),
         load_data->path,
         (unsigned)_len,
         msg_hash_to_str(MSG_BYTES));

   if (_len < 0 || !buf)
      goto error;

   /* This means we're backing up the file in memory,
    * so content_undo_save_state()
    * can restore it */
   if (load_data->flags & SAVE_TASK_FLAG_LOAD_TO_BACKUP_BUFF)
   {
      /* If we were previously backing up a file, let go of it first */
      if (undo_save_buf.data)
      {
         free(undo_save_buf.data);
         undo_save_buf.data = NULL;
      }

      if (!(undo_save_buf.data = malloc(_len)))
         goto error;

      memcpy(undo_save_buf.data, buf, _len);
      undo_save_buf.size = _len;
      strlcpy(undo_save_buf.path, load_data->path, sizeof(undo_save_buf.path));

      free(buf);
      free(load_data);
      return;
   }

   if (     savefile_list
         && savefile_list->size
         && config_get_ptr()->bools.block_sram_overwrite
      )
   {
      RARCH_LOG("[SRAM] %s.\n",
            msg_hash_to_str(MSG_BLOCKING_SRAM_OVERWRITE));

      if ((blocks = (struct sram_block*)
         calloc(savefile_list->size, sizeof(*blocks))))
      {
         num_blocks = (unsigned)savefile_list->size;
         for (i = 0; i < num_blocks; i++)
            blocks[i].type = savefile_list->elems[i].attr.i;
      }
   }

   for (i = 0; i < num_blocks; i++)
   {
      retro_ctx_memory_info_t mem_info;

      mem_info.id    = blocks[i].type;
      core_get_memory(&mem_info);

      blocks[i].size = mem_info.size;
   }

   for (i = 0; i < num_blocks; i++)
      if (blocks[i].size)
         blocks[i].data = malloc(blocks[i].size);

   /* Backup current SRAM which is overwritten by unserialize. */
   for (i = 0; i < num_blocks; i++)
   {
      if (blocks[i].data)
      {
         retro_ctx_memory_info_t mem_info;
         const void *ptr = NULL;

         mem_info.id     = blocks[i].type;

         core_get_memory(&mem_info);

         if ((ptr = mem_info.data))
            memcpy(blocks[i].data, ptr, blocks[i].size);
      }
   }

   /* Backup the current state so we can undo this load */
   content_save_state("RAM", false);

   ret = content_deserialize_state(buf, _len);

   /* Flush back. */
   for (i = 0; i < num_blocks; i++)
   {
      if (blocks[i].data)
      {
         retro_ctx_memory_info_t    mem_info;
         void *ptr   = NULL;

         mem_info.id = blocks[i].type;

         core_get_memory(&mem_info);

         if ((ptr = mem_info.data))
            memcpy(ptr, blocks[i].data, blocks[i].size);
      }
   }

   for (i = 0; i < num_blocks; i++)
      free(blocks[i].data);
   free(blocks);

   if (!ret)
      goto error;

   free(buf);
   free(load_data);

   return;

error:
   RARCH_ERR("[State] %s \"%s\".\n",
         msg_hash_to_str(MSG_FAILED_TO_LOAD_STATE),
         load_data->path);
   if (buf)
      free(buf);
   free(load_data);
}

bool content_save_state(const char *path, bool save_to_disk)
{
   size_t _len;
   void *data  = NULL;

   if (!core_info_current_supports_savestate())
   {
      RARCH_LOG("[State] %s\n",
            msg_hash_to_str(MSG_CORE_DOES_NOT_SUPPORT_SAVESTATES));
      return false;
   }

   _len = core_serialize_size();
   if (_len == 0)
      return false;

   if (!save_state_in_background)
   {
      if (!(data = content_get_serialized_data(&_len)))
      {
         RARCH_ERR("[State] %s \"%s\".\n",
               msg_hash_to_str(MSG_FAILED_TO_SAVE_STATE_TO),
               path);
         return false;
      }

      RARCH_LOG("[State] %s \"%s\", %u %s.\n",
            msg_hash_to_str(MSG_SAVING_STATE),
            path,
            (unsigned)_len,
            msg_hash_to_str(MSG_BYTES));
   }

   if (save_to_disk)
   {
      if (path_is_valid(path))
      {
         /* Before overwriting the savestate file, load it into a buffer
         to allow undo_save_state() to work */
         /* TODO/FIXME - Use msg_hash_to_str here */
         RARCH_LOG("[State] %s...\n",
               msg_hash_to_str(MSG_FILE_ALREADY_EXISTS_SAVING_TO_BACKUP_BUFFER));
         task_push_load_and_save_state(path, data, _len, true, false);
      }
      else
         task_push_save_state(path, data, _len, false);
   }
   else
   {
      if (!data)
      {
         if (!(data = content_get_serialized_data(&_len)))
         {
            RARCH_ERR("[State] %s \"%s\".\n",
                  msg_hash_to_str(MSG_FAILED_TO_SAVE_STATE_TO),
                  path);
            return false;
         }
      }

      /* save_to_disk is false, which means we are saving the state
      in undo_load_buf to allow content_undo_load_state() to restore it */

      /* If we were holding onto an old state already, clean it up first */
      if (undo_load_buf.data)
      {
         free(undo_load_buf.data);
         undo_load_buf.data = NULL;
      }

      if (!(undo_load_buf.data = malloc(_len)))
      {
         free(data);
         return false;
      }

      memcpy(undo_load_buf.data, data, _len);
      free(data);
      undo_load_buf.size = _len;
      strlcpy(undo_load_buf.path, path, sizeof(undo_load_buf.path));
   }

   return true;
}
