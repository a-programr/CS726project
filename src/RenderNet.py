import numpy as np
import tensorflow as tf
# import matplotlib.pyplot as plt
import ops
import glob
import os


class RenderNet:

    def __init__(self, sess=tf.Session(), image_size=(64, 64),
                 input_size=23, n_iterations=50, batch_size=64, lrate=0.001):
        self.image_size = image_size
        self.input_size = input_size
        self.n_pixels = self.image_size[0] * self.image_size[1] * 3  # number of channels
        self.n_iterations = n_iterations
        self.batch_size = batch_size
        self.lrate = lrate
        self.session = sess
        self.base_dim = 512

        # Network architecture
        with tf.variable_scope("rendernet"):
            self.img_params = tf.placeholder(tf.float32, shape=[batch_size, self.input_size], name='input')
            self.final_image = tf.placeholder(tf.float32, shape=[batch_size, image_size[0], image_size[1], 3],
                                              name='final_image')

            self.prediction = self.render(self.img_params)
            self.loss = tf.reduce_mean(ops.l2norm_sqrd(self.prediction, self.final_image))
            self.optimizer = tf.train.AdamOptimizer(self.lrate).minimize(self.loss)
            self.saver = tf.train.Saver()

    def render(self, img_params, reuse=False):
        if reuse:
            tf.get_variable_scope().reuse_variables()

        fc_size = ops.linear(img_params[:, 0:3], 3, 256, activation=tf.nn.relu, scope='fc_size')
        fc_view = ops.linear(img_params[:, 3:5], 2, 256, activation=tf.nn.relu, scope='fc_view')
        fc_colors = ops.linear(img_params[:, 5:23], 18, 512, activation=tf.nn.relu, scope='fc_colors')

        conc_data = tf.concat(1, [fc_size, fc_view, fc_colors])

        h1 = ops.linear(conc_data, 1024, 1024, activation=ops.lrelu, scope='h1')
        h2 = tf.reshape(ops.linear(h1, 1024, self.base_dim*4*4, activation=ops.lrelu, scope='h2'),
                        [-1, 4, 4, self.base_dim])
        h3 = ops.lrelu(ops.deconv2d(h2, [self.batch_size, 8, 8, self.base_dim/8], name='h3'))
        h4 = ops.lrelu(ops.deconv2d(h3, [self.batch_size, 16, 16, self.base_dim/16], name='h4'))
        h5 = ops.lrelu(ops.deconv2d(h4, [self.batch_size, 32, 32, self.base_dim/32], name='h5'))
        prediction = tf.nn.tanh(ops.deconv2d(h5, [self.batch_size, 64, 64, 3], name='prediction'))
        return prediction

    def train(self):
        if not os.path.exists(os.path.join("data", "train")):
            print "No training files found. Training aborted. =("
            return

        dataset_files = glob.glob("data/train/*.png")
        dataset_files.sort(key=ops.alphanum_key)
        dataset_files = np.array(dataset_files)
        dataset_params = np.load("train_params.npy")

        n_files = dataset_params.shape[0]

        testset_idxs = np.random.choice(range(n_files), self.batch_size)
        test_imgs = ops.load_imgbatch(dataset_files[testset_idxs])
        training_step = 0

        self.session.run(tf.initialize_all_variables())
        for epoch in xrange(self.n_iterations):

            rand_idxs = np.random.permutation(range(n_files))
            n_batches = n_files // self.batch_size

            for batch_i in xrange(n_batches):
                idxs_i = rand_idxs[batch_i * self.batch_size: (batch_i + 1) * self.batch_size]
                imgs_batch = ops.load_imgbatch(dataset_files[idxs_i])
                self.session.run(self.optimizer, feed_dict={self.img_params: dataset_params[idxs_i, :],
                                                            self.final_image: imgs_batch})
                training_step += 1

                current_loss = self.session.run(self.loss, feed_dict={self.img_params: dataset_params[testset_idxs, :],
                                                                      self.final_image: test_imgs})

                print "Epoch {}/{}, Batch {}/{}, Loss {}".format(epoch + 1, self.n_iterations,
                                                                 batch_i + 1, n_batches, current_loss)

                # Save checkpoint
                if training_step % 1000 == 0:
                    if not os.path.exists("checkpoint"):
                        print "Checkpoint folder not found. Creating one..."
                        os.makedirs("checkpoint")
                        print "Done."
                    self.saver.save(self.session, 'checkpoint/model.ckpt', global_step=training_step)

    def forward_batch(self, render_params):
        self.load("checkpoint")
        img = np.array(self.prediction.eval(session=self.session, feed_dict={self.img_params: render_params}))
        return img

    def load(self, ckpt_folder):
        ckpt = tf.train.get_checkpoint_state(ckpt_folder)
        if ckpt and ckpt.model_checkpoint_path:
            self.saver.restore(self.session, ckpt.model_checkpoint_path)
        else:
            print "No saved model found. Train the network first."

    def test(self):
        test_files = glob.glob("data/test/*.png")
        test_files.sort(key=ops.alphanum_key)
        test_files = np.array(test_files)
        test_params = np.load("test_params.npy")

        n_files = test_params.shape[0]

        test_idxs = np.random.choice(range(n_files), self.batch_size)
        test_imgs = ops.load_imgbatch(test_files[test_idxs])

        ops.save_images(test_imgs, [8, 8], 'ground_truth.png')

        result_imgs = self.forward_batch(test_params[test_idxs, :])
        ops.save_images(result_imgs, [8, 8], 'test_results.png')

    def architecture_check(self):
        with tf.Session() as sess:
            sess.run(tf.initialize_all_variables())
        ops.show_graph_operations()


def main():
    rnet = RenderNet()
    # rnet.train()
    rnet.test()


if __name__ == '__main__':
    main()
