from audioop import bias
import torch
import torch.nn as nn
# import torch.nn.functional as F
import transformer as trans
# import Transformer_aladdinpersson as trans_2
# from transformers import XLNetTokenizer, XLNetForSequenceClassification, XLNetModel, AdamW

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

class multitaskNet(nn.Module):
    def __init__(self, hidden_size, sent_len, embed_len, dropout, device, vocab_size, num_layers, att_heads, mult,
                 pad_idx,valence=True, arousal=True, quad=True, dom=True, w2v=None):
        super(multitaskNet, self).__init__()
        self.device = device
        self.pos_emb = nn.Embedding(sent_len, embed_len)
        if w2v is not None:
            self.word_emb = nn.Embedding(vocab_size, embed_len, pad_idx)
            self.word_emb.load_state_dict({'weight' : w2v})
        else:
            self.word_emb = nn.Embedding(vocab_size, embed_len, pad_idx)
        self.enc_manual = trans.Encoder(vocab_size, embed_len, num_layers, att_heads, mult, dropout, sent_len, device, w2v)
        self.enc_manual.double()
        enc_layer = nn.TransformerEncoderLayer(embed_len, att_heads, mult, dropout, batch_first=True)
        self.enc = nn.TransformerEncoder(enc_layer, num_layers)
        #self.pretrained_trans = XLNetForSequenceClassification.from_pretrained("xlnet-base-cased", num_labels=embed_len)
        self.use_valence = valence
        self.use_arousal = arousal
        self.use_dom = dom
        self.use_quad = quad
        self.dropout = nn.Dropout(dropout)
        self.sequence_summary = nn.Sequential(
                                            nn.Flatten(), #flatten sequence, heads and embedding dimensions
                                            nn.Linear(sent_len * embed_len, embed_len), # first linear stage compresses sequence dim
                                            nn.ReLU(),
                                            nn.Linear(embed_len, 2 * hidden_size)                         # sencond stage compresses embedding dim
                                            )
        
        self.fc_1 = nn.Sequential(nn.ReLU(), nn.Dropout(dropout), nn.Linear(2 * hidden_size, hidden_size))
        self.fc_valence = nn.Linear(hidden_size, 2, bias=False)
        self.fc_arousal = nn.Linear(hidden_size, 2, bias=False)
        self.fc_dominance = nn.Linear(hidden_size, 2, bias=False)
        self.fc_quad = nn.Sequential(nn.ReLU(), nn.Linear(hidden_size, 4))

    def forward(self, x, version):
        '''
        transformer needs to output dimension: BxLxHxE (sum out the embedding dim)
        B = batch size, L = sentence length, H = number of attention heads, E = embedding size
        '''
        if version == 0:
            #Create embeddings first
            N, seq_length = x.shape
            positions = torch.arange(0,seq_length).expand(N,seq_length).to(self.device)
            x = self.dropout(self.word_emb(x) + self.pos_emb(positions))
            #Now run transformer encoders
            out = self.enc(x)  #BxLxHxE
        elif version == 1:
            out = self.enc_manual(x)
        elif version == 2:
            with torch.no_grad():
                out = self.pretrained_trans(x).logits
        #print(out.shape)        

        out = self.sequence_summary(out)                #BxH
        out = self.fc_1(out)                            #BxH
        if self.use_quad:
            return self.fc_quad(out)
        if self.use_valence:
            return self.fc_valence(out)
        if self.use_arousal:
            return self.fc_arousal(out)
        if self.use_dom:
            return self.use_dom(out)
