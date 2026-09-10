export type Autor = "usuario" | "juri"

export interface Mensagem {
  id: string
  autor: Autor
  texto: string
}
