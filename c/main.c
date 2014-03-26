/**
 * Looping video player.
 */
#include <clutter/clutter.h>
#include <clutter-gst/clutter-gst.h>
#include <stdlib.h>

#define SEEK_H 14
#define SEEK_W 440
#define GST_PLAY_FLAG_VIS 1 << 3

typedef struct _VideoApp
{
  ClutterActor *stage;
  ClutterActor *vtexture;
} VideoApp;

static gboolean opt_fullscreen = FALSE;
static gboolean opt_loop = FALSE;

static GOptionEntry options[] =
{
  { "fullscreen",
    'f', 0,
    G_OPTION_ARG_NONE,
    &opt_fullscreen,
    "Start the player in fullscreen",
    NULL },

  { "loop",
    'l', 0,
    G_OPTION_ARG_NONE,
    &opt_loop,
    "Start the video again once reached the EOS",
    NULL },

  { NULL }
};

static gboolean
input_cb (ClutterStage *stage,
          ClutterEvent *event,
          gpointer      user_data)
{
  VideoApp *app = (VideoApp*)user_data;
  gboolean handled = FALSE;

  switch (event->type)
    {
    case CLUTTER_KEY_PRESS:
      {
        switch (clutter_event_get_key_symbol (event))
          {
          case CLUTTER_q:
          case CLUTTER_Escape:
            clutter_actor_destroy (app->stage);
            break;

          default:
            break;
          }
      }

    default:
      break;
    }

  return handled;
}

static void
size_change (ClutterTexture *texture,
             gint            base_width,
             gint            base_height,
             VideoApp       *app)
{
  ClutterActor *stage = app->stage;
  gfloat new_x, new_y, new_width, new_height;
  gfloat stage_width, stage_height;
  gfloat frame_width, frame_height;

  clutter_actor_get_size (stage, &stage_width, &stage_height);

  /* base_width and base_height are the actual dimensions of the buffers before
   * taking the pixel aspect ratio into account. We need to get the actual
   * size of the texture to display */
  clutter_actor_get_size (CLUTTER_ACTOR (texture), &frame_width, &frame_height);

  new_height = (frame_height * stage_width) / frame_width;
  if (new_height <= stage_height)
    {
      new_width = stage_width;

      new_x = 0;
      new_y = (stage_height - new_height) / 2;
    }
  else
    {
      new_width  = (frame_width * stage_height) / frame_height;
      new_height = stage_height;

      new_x = (stage_width - new_width) / 2;
      new_y = 0;
    }

  clutter_actor_set_position (CLUTTER_ACTOR (texture), new_x, new_y);
  clutter_actor_set_size (CLUTTER_ACTOR (texture), new_width, new_height);
}

static void
on_stage_allocation_changed (ClutterActor           *stage,
                             ClutterActorBox        *box,
                             ClutterAllocationFlags  flags,
                             VideoApp               *app)
{
}

static void
on_video_texture_eos (ClutterMedia *media,
                      VideoApp     *app)
{
  if (opt_loop)
    {
      clutter_media_set_progress (media, 0.0);
      clutter_media_set_playing (media, TRUE);
    }
}

int
main (int argc, char *argv[])
{
  VideoApp            *app = NULL;
  GstElement          *pipe;
  GstElement          *playsink;
  GstElement          *goomsource;
  GstIterator         *iter;
  ClutterActor        *stage;
  ClutterColor         stage_color = { 0x00, 0x00, 0x00, 0x00 };
  GError              *error = NULL;
  GValue               value = { 0, };
  char                *sink_name;
  int                  playsink_flags;

  clutter_gst_init_with_args (&argc,
                              &argv,
                              " - A simple video player",
                              options,
                              NULL,
                              &error);
  if (error)
    {
      g_print ("%s\n", error->message);
      g_error_free (error);
      return EXIT_FAILURE;
    }

  if (argc < 2)
    {
      g_print ("Usage: %s [OPTIONS] <video file>\n", argv[0]);
      return EXIT_FAILURE;
    }

  stage = clutter_stage_new ();
  clutter_actor_set_background_color (stage, &stage_color);
  clutter_actor_set_size (stage, 768, 576);
  clutter_stage_set_minimum_size (CLUTTER_STAGE (stage), 640, 480);
  if (opt_fullscreen)
    clutter_stage_set_fullscreen (CLUTTER_STAGE (stage), TRUE);

  app = g_new0(VideoApp, 1);
  app->stage = stage;
  app->vtexture = clutter_gst_video_texture_new ();

  if (app->vtexture == NULL)
    g_error("failed to create vtexture");

  g_signal_connect (app->vtexture, "eos",
                    G_CALLBACK (on_video_texture_eos), app);

  g_signal_connect (stage, "allocation-changed",
                    G_CALLBACK (on_stage_allocation_changed), app);

  g_signal_connect (stage, "destroy",
                    G_CALLBACK (clutter_main_quit), NULL);

  /* Handle it ourselves so can scale up for fullscreen better */
  g_signal_connect_after (CLUTTER_TEXTURE (app->vtexture),
                          "size-change",
                          G_CALLBACK (size_change), app);

  /* Load up out video texture */
  clutter_media_set_filename (CLUTTER_MEDIA (app->vtexture), argv[1]);

  /* Set up things so that a visualisation is played if there's no video */
  pipe = clutter_gst_video_texture_get_pipeline (CLUTTER_GST_VIDEO_TEXTURE (app->vtexture));
  if (! pipe)
    g_error ("Unable to get gstreamer pipeline!\n");

  iter = gst_bin_iterate_sinks (GST_BIN (pipe));
  if (! iter)
    g_error ("Unable to iterate over sinks!\n");
  while (gst_iterator_next (iter, &value) == GST_ITERATOR_OK)
  {
    playsink = g_value_get_object (&value);
    sink_name = gst_element_get_name (playsink);
    if (g_strcmp0 (sink_name, "playsink") != 0) {
      g_free (sink_name);
      break;
    }
    g_free (sink_name);
  }
  gst_iterator_free (iter);
  goomsource = gst_element_factory_make ("goom", "source");
  if (!goomsource)
    g_error ("Unable to create goom visualiser!\n");
  g_object_get (playsink, "flags", &playsink_flags, NULL);
  playsink_flags |= GST_PLAY_FLAG_VIS;
  g_object_set (playsink,
                "vis-plugin", goomsource,
                "flags", playsink_flags,
                NULL);
  /* Hook up other events */
  g_signal_connect (stage, "event", G_CALLBACK (input_cb), app);
  clutter_media_set_playing (CLUTTER_MEDIA (app->vtexture), TRUE);
  clutter_actor_show (stage);
  clutter_main ();

  return EXIT_SUCCESS;
}
