import torch
import torchx as tx
import torchx.nn as nnx
import torch.nn as nn
import torchx.layers as L
import numpy as np

class CNNStemNetwork(nnx.Module):
    def __init__(self, D_obs, D_out, use_layernorm=True):
        super(CNNStemNetwork, self).__init__()
        conv_channels=[16, 32]
        self.model = L.Sequential(
            L.Conv2d(conv_channels[0], kernel_size=8, stride=4),
            L.ReLU(),
            L.Conv2d(conv_channels[1], kernel_size=4, stride=2),
            L.ReLU(),
            L.Flatten(),
            L.Linear(D_out),
            L.ReLU(),
        )

        # instantiate parameters
        self.model.build((None, *D_obs))

    def forward(self, obs):
        obs_shape = obs.size()
        if_high_dim = (len(obs_shape) == 5)
        if if_high_dim: # case of RNN input
            obs = obs.view(-1, *obs_shape[2:])  

        obs = self.model(obs)

        if if_high_dim:
            obs = obs.view(obs_shape[0], obs_shape[1], -1)
        return obs

class ActorNetworkX(nnx.Module):
    def __init__(self, D_in, D_act, hidden_size=200, use_layernorm=True):
        super(ActorNetworkX, self).__init__()
        xp_input = L.Placeholder((None, D_in))
        xp = L.Linear(hidden_size)(xp_input)
        xp = L.ReLU()(xp)
        if use_layernorm:
            # Normalize 1 dimension
            xp = L.LayerNorm(1)(xp)
        xp = L.Linear(D_act)(xp)
        xp = L.Tanh()(xp)

        self.model = L.Functional(inputs=xp_input, outputs=xp)
        self.model.build((None, D_in))

    def forward(self, obs):
        return self.model(obs)

class CriticNetworkX(nnx.Module):
    def __init__(self, D_in, D_act, hidden_size=300, use_layernorm=True):
        super(CriticNetworkX, self).__init__()
        xp_input = L.Placeholder((None, D_in + D_act))

        xp = L.Linear(hidden_size)(xp_input)
        xp = L.ReLU()(xp)
        if use_layernorm:
            # Normalize 1 dimension
            xp = L.LayerNorm(1)(xp)
        xp = L.Linear(1)(xp)

        self.model = L.Functional(inputs=xp_input, outputs=xp)
        self.model.build((None, D_in + D_act))

    def forward(self, obs, action):
        x = torch.cat((obs, action), dim=1)
        return self.model(x)

class ActorNetwork(nnx.Module):
    '''
    For use with flat observations
    '''

    def __init__(self, D_obs, D_act, hidden_sizes=[64, 64], use_batchnorm=False):
        super(ActorNetwork, self).__init__()

        xp_input = L.Placeholder((None, D_obs))
        xp = L.Linear(hidden_sizes[0])(xp_input)
        xp = L.ReLU()(xp)
        xp = L.Linear(hidden_sizes[1])(xp)
        xp = L.ReLU()(xp)
        xp = L.Linear(D_act)(xp)
        xp = L.Tanh()(xp)

        self.model = L.Functional(inputs=xp_input, outputs=xp)
        self.model.build((None, D_obs))

    def forward(self, obs):
        return self.model(obs)

class CriticNetwork(nnx.Module):

    def __init__(self, D_obs, D_act, hidden_sizes=[64, 64], use_batchnorm=False):
        super(CriticNetwork, self).__init__()

        xp_input_obs = L.Placeholder((None, D_obs))
        xp = L.Linear(hidden_sizes[0])(xp_input_obs)
        xp = L.ReLU()(xp)
        self.model_obs = L.Functional(inputs=xp_input_obs, outputs=xp)
        self.model_obs.build((None, D_obs))

        xp_input_concat = L.Placeholder((None, hidden_sizes[0] + D_act))
        xp = L.Linear(hidden_sizes[1])(xp_input_concat)
        xp = L.ReLU()(xp)
        xp = L.Linear(1)(xp)

        self.model_concat = L.Functional(inputs=xp_input_concat, outputs=xp)
        self.model_concat.build((None, D_act + hidden_sizes[0]))

    def forward(self, obs, act):
        h_obs = self.model_obs(obs)
        h1 = torch.cat((h_obs, act), 1)
        value = self.model_concat(h1)
        return value


class PPO_ActorNetwork(nnx.Module):
    '''
        PPO custom actor network structure
    '''
    def __init__(self, D_obs, D_act, hidden_sizes=[64, 64], init_log_sig=0):
        super(PPO_ActorNetwork, self).__init__()
        # assumes D_obs here is the correct RNN hidden dim
        xp_input = L.Placeholder((None, D_obs))
        xp = L.Linear(hidden_sizes[0])(xp_input)
        xp = L.Tanh()(xp)
        xp = L.Linear(hidden_sizes[1])(xp)
        xp = L.Tanh()(xp)
        xp = L.Linear(D_act)(xp)

        self.model = L.Functional(inputs=xp_input, outputs=xp)
        self.model.build((None, D_obs))

        self.log_var = nn.Parameter(torch.zeros(1, D_act) + init_log_sig)

    def forward(self, obs):
        obs_shape = obs.size()
        if_high_dim = (len(obs_shape) == 3)
        if if_high_dim: 
            obs = obs.view(-1, obs_shape[2])

        mean = self.model(obs)
        std  = torch.exp(self.log_var) * torch.ones(mean.size())

        action = torch.cat((mean, std), dim=1)
        if if_high_dim:
            action = action.view(obs_shape[0], obs_shape[1], -1)
        return action


class PPO_CriticNetwork(nnx.Module):
    '''
        PPO custom critic network structure
    '''
    def __init__(self, D_obs, hidden_sizes=[64, 64]):
        super(PPO_CriticNetwork, self).__init__()
        # assumes D_obs here is the correct RNN hidden dim if necessary

        xp_input = L.Placeholder((None, D_obs))
        xp = L.Linear(hidden_sizes[0])(xp_input)
        xp = L.Tanh()(xp)
        xp = L.Linear(hidden_sizes[1])(xp)
        xp = L.Tanh()(xp)
        xp = L.Linear(1)(xp)

        self.model = L.Functional(inputs=xp_input, outputs=xp)
        self.model.build((None, D_obs))

    def forward(self, obs):
        obs_shape = obs.size()
        if_high_dim = (len(obs_shape) == 3)
        if if_high_dim: 
            obs = obs.view(-1, obs_shape[2])

        v = self.model(obs)

        if if_high_dim:
            v = v.view(obs_shape[0], obs_shape[1], 1)
        return v

