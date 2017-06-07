from __future__ import print_function

import argparse
import h5py

import numpy as np

from keras import backend as K
from keras import optimizers
from keras.models import Model, Sequential
from keras.layers import Activation, Dense, Dropout, Input
from keras.initializers import RandomUniform
from keras.callbacks import Callback, ModelCheckpoint
from scipy.stats.stats import pearsonr

import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from sklearn.metrics import r2_score

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

import p1b1
import p1_common
import p1_common_keras


def get_p1b1_parser():
	parser = argparse.ArgumentParser(prog='p1b1_baseline', formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Train Autoencoder - Pilot 1 Benchmark 1')
	return p1b1.common_parser(parser)


class MyHistory(Callback):
    def on_epoch_begin(self, epoch, logs=None):
        print("\n")

    def on_epoch_end(self, epoch, logs=None):
        y_pred = self.model.predict(self.validation_data[0])
        r2 = r2_score(self.validation_data[1], y_pred)
        corr, _ = pearsonr(self.validation_data[1].flatten(), y_pred.flatten())
        # print("\nval_r2:", r2)
        # print(y_pred.shape)
        print("\nval_corr:", corr, "val_r2:", r2)
        print("\n")


def main():
    # Get command-line parameters
    parser = get_p1b1_parser()
    args = parser.parse_args()
    #print('Args:', args)
    # Get parameters from configuration file
    fileParameters = p1b1.read_config_file(args.config_file)
    #print ('Params:', fileParameters)
    # Consolidate parameter set. Command-line parameters overwrite file configuration
    gParameters = p1_common.args_overwrite_config(args, fileParameters)
    print('Params:', gParameters)

    # Construct extension to save model
    ext = p1b1.extension_from_parameters(gParameters, '.keras')
    logfile = args.logfile if args.logfile else args.save+ext+'.log'
    p1b1.logger.info('Params: {}'.format(gParameters))

    # Get default parameters for initialization and optimizer functions
    kerasDefaults = p1_common.keras_default_config()
    seed = gParameters['rng_seed']

    # Load dataset
    # X_train, X_val, X_test = p1b1.load_data(gParameters, seed)
    # with h5py.File('x_cache.h5', 'w') as hf:
        # hf.create_dataset("train",  data=X_train)
        # hf.create_dataset("val",  data=X_val)
        # hf.create_dataset("test",  data=X_test)

    with h5py.File('x_cache.h5', 'r') as hf:
        X_train = hf['train'][:]
        X_val = hf['val'][:]
        X_test = hf['test'][:]

    print("Shape X_train: ", X_train.shape)
    print("Shape X_val: ", X_val.shape)
    print("Shape X_test: ", X_test.shape)

    print("Range X_train --> Min: ", np.min(X_train), ", max: ", np.max(X_train))
    print("Range X_val --> Min: ", np.min(X_val), ", max: ", np.max(X_val))
    print("Range X_test --> Min: ", np.min(X_test), ", max: ", np.max(X_test))

    input_dim = X_train.shape[1]
    output_dim = input_dim
    input_vector = Input(shape=(input_dim,))

    # Initialize weights and learning rule
    initializer_weights = p1_common_keras.build_initializer(gParameters['initialization'], kerasDefaults, seed)
    initializer_bias = p1_common_keras.build_initializer('constant', kerasDefaults, 0.)

    activation = gParameters['activation']

    # Define Autoencoder architecture
    layers = gParameters['dense']

    if layers != None:
        if type(layers) != list:
            layers = list(layers)
        # Encoder Part
        for i, l in enumerate(layers):
            if i == 0:
                encoded = Dense(l, activation=activation,
                                kernel_initializer=initializer_weights,
                                bias_initializer=initializer_bias)(input_vector)
            else:
                encoded = Dense(l, activation=activation,
                                kernel_initializer=initializer_weights,
                                bias_initializer=initializer_bias)(encoded)
        # Decoder Part
        for i, l in reversed(list(enumerate(layers))):
            if i < len(layers) - 1:
                if i == len(layers) - 2:
                    decoded = Dense(l, activation=activation,
                                    kernel_initializer=initializer_weights,
                                    bias_initializer=initializer_bias)(encoded)
                else:
                    decoded = Dense(l, activation=activation,
                                    kernel_initializer=initializer_weights,
                                    bias_initializer=initializer_bias)(decoded)
        decoded = Dense(input_dim, kernel_initializer=initializer_weights,
                        bias_initializer=initializer_bias)(decoded)
    else:
        decoded = Dense(input_dim, kernel_initializer=initializer_weights,
                        bias_initializer=initializer_bias)(input_vector)

    # Build Autoencoder model
    ae = Model(outputs=decoded, inputs=input_vector)
    p1b1.logger.debug('Model: {}'.format(ae.to_json()))

    # Define optimizer
    optimizer = p1_common_keras.build_optimizer(gParameters['optimizer'],
                                                gParameters['learning_rate'],
                                                kerasDefaults)

    # Compile and display model
    ae.compile(loss=gParameters['loss'], optimizer=optimizer)
    ae.summary()

    # Seed random generator for training
    np.random.seed(seed)

    X_val2 = np.copy(X_val)
    np.random.shuffle(X_val2)
    print(X_val.shape)
    print(X_val2.shape)
    start_scores = p1b1.evaluate_autoencoder(X_val, X_val2)
    print('\nBetween random permutations of validation data:', start_scores)

    ae.fit(X_train, X_train,
           batch_size=gParameters['batch_size'],
           epochs=gParameters['epochs'],
           callbacks=[MyHistory()],
           validation_data=(X_val, X_val))

    # model save
    #save_filepath = "model_ae_W_" + ext
    #ae.save_weights(save_filepath)

    # Evalute model on test set
    X_pred = ae.predict(X_test)
    scores = p1b1.evaluate_autoencoder(X_pred, X_test)
    print('\nEvaluation on test data:', scores)

    diff = X_pred - X_test
    plt.hist(diff.ravel(), bins='auto')
    plt.title("Histogram of Errors with 'auto' bins")
    plt.savefig('histogram_keras.png')


if __name__ == '__main__':
    main()
    try:
        K.clear_session()
    except AttributeError:      # theano does not have this function
        pass
