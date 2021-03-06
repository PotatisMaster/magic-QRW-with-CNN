# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 16:29:26 2020

@author: hanna
"""
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import time
from corpus_generator import *
from QRWCNN_arch import *
import tensorflow as tf
from tensorflow.keras.utils import plot_model
from sklearn.metrics import f1_score, precision_score, recall_score

# Saving files
import os, inspect  # for current directory
current_file_directory = os.path.dirname(os.path.abspath(__file__))



os.environ["CUDA_VISIBLE_DEVICES"] = "1"
tf.config.list_physical_devices('GPU')



names = ['c', 'q', 'positive', 'negative', 'T', 'H']
comp_list = [0, 1] 
num_classes = len(comp_list)
names = [names[x] for x in comp_list]

magic = True
if magic:
    file_name = current_file_directory + '/results_linear_magic'
else:
    file_name = current_file_directory + '/results_linear'

def gen_data(n_max = 10, n = 5, N = 100, linear = True, cyclic = False, all_graphs = False, duplicates=False, magic=False):
    corpus = Corpus_n(n_max = n_max, target = 1, initial = 0)
    corpus.generate_graphs(n = n, N = N, percentage = False, random = False, linear = linear, cyclic = cyclic, all_graphs = all_graphs, duplicates=duplicates, magic=magic)
    print('-'*10 + ' Corpus done! ' + '-'*10)
    
    N = len(corpus.corpus_list)
    data_X = np.ones((N, n, n))
    data_labels = np.ones((N, corpus.corpus_list[0].label.shape[0]))
    data_ranking = np.ones((N, corpus.corpus_list[0].ranking.shape[0]))
    for i in range(N):
        data_X[i] = corpus.corpus_list[i].A
        data_labels[i] = corpus.corpus_list[i].label # categorical, learned embedding
        data_ranking[i] = corpus.corpus_list[i].ranking # 2 dim np array, categorical

    data_X = data_X.reshape(N, n, n, 1) # [samples, rows, columns, channels]
    
    if magic:
        np.savez(current_file_directory + '/linear_corpuses_magic' +'/train_val_test_data' + str(n), data_X, data_labels, data_ranking)
    else:
        np.savez(current_file_directory + '/linear_corpuses' +'/train_val_test_data' + str(n), data_X, data_labels, data_ranking)

def load_data(filename):
    file = np.load(filename)
    data_X = file['arr_0']
    data_labels = file['arr_1']
    data_ranking = file['arr_2']
    return data_X, data_labels, data_ranking

def choose_types(comp_list, data_ranking):
    mask = np.zeros(data_ranking.shape[1], dtype=bool)
    mask[comp_list] = True
    data_ranking_comp = data_ranking[:, mask]
    data_label_comp = np.zeros((data_ranking.shape[0], len(comp_list)))
    for i in range(data_ranking.shape[0]):
        temp = data_ranking_comp[i, :]
        data_label_comp[i] = np.where(temp == temp.min(), 1.0, 0.0)
    return data_label_comp

def delete_ties(X, y, batch_size = 1):
    mask = np.sum(y, axis=1) == 1.
    print('\nNumber of ties: ', X.shape[0] - np.sum(mask))
    X = X[mask]
    y = y[mask]
    if not (X.shape[0] % batch_size == 0):
        size = 1
        for i in range(batch_size+2):
            if ((X.shape[0] - i) % batch_size == 0):
                size = (X.shape[0] - i)
                break
        X = X[:size, :, :, :]

    if not (y.shape[0] % batch_size == 0):
        size = 1
        for i in range(batch_size+2):
            if ((y.shape[0] - i) % batch_size == 0):
                size = (y.shape[0] - i)
                break
        y = y[:size]
    return X, y

y_upper = 1.0
epochs = 100
colors = [(51, 51, 51), (76, 32, 110), (32, 92, 25), (32, 95, 105), (110, 32, 106), (189, 129, 9)]# ['grey', 'purple', 'green', 'blue', 'magenta', 'orange']
colors = [tuple(t/250 for t in x) for x in colors]

validation_freq = 1

average_num = 50
n_min_loop = 7
n_max_loop = 9
training_time = np.zeros((n_max_loop-n_min_loop,average_num))
reg = (0.0, 0.0)
dropout_rate = 0.0
batch_size = 1
net_type = 1



file1 = open(file_name +'/f1_precision_recall.txt', 'w')
for n_iter in range(n_min_loop, n_max_loop):

    grande_training_loss = np.zeros((epochs, average_num))
    grande_test_accuracy = np.zeros((epochs, average_num))
    grande_test_loss = np.zeros((epochs, average_num))
    grande_precision = np.zeros((num_classes, average_num))
    grande_recall = np.zeros((num_classes, average_num))
    grande_f1 = np.zeros((num_classes, average_num))
    
    for average_iter in range(average_num):
        print('-'*20, ' average iter: ', str(average_iter), ' n: ', str(n_iter), '-'*20)
        try:
            if magic:
                data_X, data_labels, data_ranking = load_data(current_file_directory + '/linear_corpuses_magic' +'/train_val_test_data'+str(n_iter)+'.npz')
            else:
                data_X, data_labels, data_ranking = load_data(current_file_directory + '/linear_corpuses' +'/train_val_test_data'+str(n_iter)+'.npz')
        except:
            if magic:
                gen_data(n_max = n_iter, n = n_iter, linear = True, cyclic = False, all_graphs = False, duplicates = True, magic = True)
                data_X, data_labels, data_ranking = load_data(current_file_directory + '/linear_corpuses_magic'+'/train_val_test_data'+str(n_iter)+'.npz')
            else:
                gen_data(n_max = n_iter, n = n_iter, linear = True, cyclic = False, all_graphs = False, duplicates = True, magic = magic)
                data_X, data_labels, data_ranking = load_data(current_file_directory + '/linear_corpuses'+'/train_val_test_data'+str(n_iter)+'.npz')

        data_labels = choose_types(comp_list, data_ranking)
        data_X, data_labels = delete_ties(data_X, data_labels)        
        
        test_size = 0.1
        X_train, X_test, y_train, y_test = train_test_split(data_X, data_labels, test_size=test_size)
        X_train, y_train, X_test, y_test = tf.convert_to_tensor(X_train), tf.convert_to_tensor(y_train), tf.convert_to_tensor(X_test), tf.convert_to_tensor(y_test)

        print('N ', X_train.shape)
        #assert len(X_train) % batch_size == 0
        #assert len(X_test) % batch_size == 0
        assert not np.any(np.isnan(y_test))
        assert np.all(np.sum(y_train, axis = 1) == 1.) # no ties
        num_classes = y_test.shape[1]

        model = ETE_ETV_Net(n_iter, num_classes, net_type=net_type, num_ETE = 2)
        model = model.build(batch_size=batch_size)
        plot_model(model, to_file=file_name + '/model_plot'+ str(n_iter) +'n.png', show_shapes=True, show_layer_names=True)
        start = time.time()
        #history = model.fit(X_train, y_train, batch_size=batch_size, steps_per_epoch = 3, validation_data = (X_test, y_test), validation_freq = validation_freq, epochs=epochs, verbose=2, shuffle=True)

        history = model.fit(X_train, y_train, batch_size=1, validation_data = (X_test, y_test), validation_freq = validation_freq, epochs=epochs, verbose=2, shuffle = True)

        end = time.time()
        vtime = end-start
        training_time[n_iter-n_min_loop, average_iter] = vtime


        y_pred1 = model.predict(X_test, batch_size=batch_size)
        y_pred=np.eye(1, num_classes, k=np.argmax(y_pred1, axis =1)[0])
        for i in range(1, y_pred1.shape[0]):
            y_pred = np.append(y_pred, np.eye(1, num_classes, k=np.argmax(y_pred1, axis = 1)[i]), axis = 0)

        grande_training_loss[:, average_iter] = history.history['loss']
        grande_test_accuracy[:, average_iter] = history.history['val_accuracy']
        grande_test_loss[:, average_iter] = history.history['val_loss']
        grande_precision[:, average_iter] = precision_score(y_test, y_pred, average=None)
        grande_recall[:, average_iter] = recall_score(y_test, y_pred, average=None)
        grande_f1[:, average_iter] = f1_score(y_test, y_pred, average=None)

    training_loss = np.average(grande_training_loss, 1)
    test_accuracy = np.average(grande_test_accuracy, 1)
    test_loss = np.average(grande_test_loss, 1)
    training_time_average = np.average(training_time, 1)
    precision = np.average(grande_precision, 1)
    recall = np.average(grande_recall, 1)
    f1 = np.average(grande_f1, 1)



    plt.figure(1)
    plt.title('Figure 3 a) Hanna code with types:'+ str(names) + ', average '+ str(average_num) + ', dropout ' + str(dropout_rate) + ', reg ' + str(reg) + ', net_type ' + str(net_type))
    plt.ylim(0.0, y_upper)
    plt.plot(np.linspace(0.0, len(training_loss), len(training_loss)), training_loss,'--', color = colors[n_iter-n_min_loop], label = 'train loss for ' + str(n_iter) + ' nodes ' + str(round(training_loss[-1],2)))
    plt.plot(np.linspace(0.0, len(test_accuracy), len(test_accuracy)), test_accuracy,'-', color = colors[n_iter-n_min_loop], label = 'test accuracy for ' + str(n_iter) + ' nodes ' + str(round(test_accuracy[-1],2)))
    plt.plot(np.linspace(0.0, len(test_loss), len(test_loss)), test_loss,'-.', color = tuple(t+0.3 for t in colors[n_iter-n_min_loop]), label = 'test loss for ' + str(n_iter) + ' nodes ' + str(round(test_loss[-1],2)))
    plt.xlabel('epochs')
    plt.ylabel('learning performance')
    plt.legend()
    np.savez(file_name +'/training_results' + str(n_iter), training_loss, test_accuracy, test_loss)

    plt.savefig(file_name+'/linear_graphs_cross_entropy_hanna_' + str(average_num))
    

    L = ['n ' + str(n_iter) + '\n' + 
    'precision: ' + str(precision)+ '\n' +
    'recall: ' + str(recall) +'\n' + 
    'f1: ' + str(f1) + '\n\n\n']
    file1.writelines(L)
file1.close()

plt.figure(2)
plt.title('Training time, Hanna code with types:' + str(names)+ ', net_type ' + str(net_type))
plt.plot(np.arange(n_min_loop, n_max_loop), training_time_average)
plt.xlabel('number of nodes')
plt.ylabel('time in seconds')
plt.savefig(file_name +'/time_linear_graphs_cross_entropy_hanna' + str(average_num))


# ------------------------------------------------
print('-'*20, ' DONE ', '-'*20)