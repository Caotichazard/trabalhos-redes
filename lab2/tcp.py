import asyncio
from tcputils import *
import os


class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)
        

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:
            print('descartando segmento com checksum incorreto')
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)
        
        if (flags & FLAGS_SYN) == FLAGS_SYN:
            # A flag SYN estar setada significa que é um cliente tentando estabelecer uma conexão nova
            # TODO: talvez você precise passar mais coisas para o construtor de conexão
            
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao,seq_no)
            
            header = make_header(conexao.id_conexao[3] , conexao.id_conexao[1] , conexao.init_seq_no , conexao.src_seq_no , FLAGS_SYN | FLAGS_ACK )
            fixed_checksum = fix_checksum(header,conexao.id_conexao[2],conexao.id_conexao[0])
            self.rede.enviar(fixed_checksum,conexao.id_conexao[0])
            #conexao.init_seq_no = conexao.init_seq_no + 1
            # TODO: você precisa fazer o handshake aceitando a conexão. Escolha se você acha melhor
            # fazer aqui mesmo ou dentro da classe Conexao.
            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao, src_seq_no):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        #self.timer = asyncio.get_event_loop().call_later(1, self._exemplo_timer)  # um timer pode ser criado assim; esta linha é só um exemplo e pode ser removida
        #self.timer.cancel()   # é possível cancelar o timer chamando esse método; esta linha é só um exemplo e pode ser removida
        self.init_seq_no = int.from_bytes(os.urandom(4),"big")
        self.src_seq_no = src_seq_no + 1
        self.is_open = 1
        
        

    def _exemplo_timer(self):
        # Esta função é só um exemplo e pode ser removida
        print('Este é um exemplo de como fazer um timer')

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # TODO: trate aqui o recebimento de segmentos provenientes da camada de rede.
        # Chame self.callback(self, dados) para passar dados para a camada de aplicação após
        # garantir que eles não sejam duplicados e que tenham sido recebidos em ordem.
        print("a")
        #print(seq_no,self.src_seq_no,len(payload))
        if(flags & FLAGS_FIN) == FLAGS_FIN:
            self.src_seq_no += 1
            header = make_header(self.id_conexao[3] , self.id_conexao[1] , self.init_seq_no , self.src_seq_no  , FLAGS_ACK )
            dados = fix_checksum(header,self.id_conexao[2],self.id_conexao[0])
            self.servidor.rede.enviar(dados,self.id_conexao[0])
            self.callback(self,b'')
            self.init_seq_no += 1
            self.is_open = 0
            
        elif self.is_open == 1 :
            expected_seq_no = self.src_seq_no 
            if seq_no  == expected_seq_no:
                self.src_seq_no = expected_seq_no  + len(payload)
                header = make_header(self.id_conexao[3] , self.id_conexao[1] , self.init_seq_no , self.src_seq_no , FLAGS_ACK )
                dados = fix_checksum(header,self.id_conexao[2],self.id_conexao[0])
                self.servidor.rede.enviar(dados,self.id_conexao[0])
                self.callback(self,payload)
                self.init_seq_no = self.init_seq_no + 1
            
        print('recebido payload: %r' % payload)

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados):
        """
        Usado pela camada de aplicação para enviar dados
        """
        # TODO: implemente aqui o envio de dados.
        # Chame self.servidor.rede.enviar(segmento, dest_addr) para enviar o segmento
        # que você construir para a camada de rede.
        #print(dados)
        #print(len(dados))
        self.servidor.rede.fila.clear()
        print(self.servidor.rede.fila)
        if len(dados) < MSS+1:
            header = make_header(self.id_conexao[3] , self.id_conexao[1] , self.init_seq_no , self.src_seq_no , FLAGS_ACK )
            segment = fix_checksum(header,self.id_conexao[2],self.id_conexao[0])
            self.servidor.rede.enviar(segment + dados, self.id_conexao[0])
            self.init_seq_no = self.init_seq_no + len(dados) -1
        else:
            for i in range((len(dados)//MSS)):
                header = make_header(self.id_conexao[3] , self.id_conexao[1] , self.init_seq_no , self.src_seq_no , FLAGS_ACK )
                segment = fix_checksum(header,self.id_conexao[2],self.id_conexao[0])
                print(len(dados[i*MSS:(i+1)*MSS]))
                payload = segment + dados[i*MSS:(i+1)*MSS]
                self.servidor.rede.enviar(payload, self.id_conexao[0])
                
                
                self.init_seq_no = self.init_seq_no + MSS
                #print("a")
            self.init_seq_no = self.init_seq_no - len(dados)//MSS
        pass

    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        # TODO: implemente aqui o fechamento de conexão

        header = make_header(self.id_conexao[3] , self.id_conexao[1] , self.init_seq_no , self.src_seq_no + 1 , FLAGS_FIN )
        dados = fix_checksum(header,self.id_conexao[2],self.id_conexao[0])
        self.servidor.rede.enviar(dados,self.id_conexao[0])
        pass
