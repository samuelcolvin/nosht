import React from 'react'
import {Link} from 'react-router-dom'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {ButtonGroup, Button} from 'reactstrap'
import requests from '../utils/requests'
import {as_title, image_thumb} from '../utils'
import MarkdownRender from './Markdown'
import {Loading} from './Errors'
import Map from './Map'
import ButtonConfirm from './Confirm'

export const render = v => {
  if (typeof v === 'boolean') {
    return <FontAwesomeIcon icon={v ? 'check' : 'times'}/>
  } else if ([null, undefined].includes(v)) {
    return <Dash/>
  } else if (typeof v === 'object') {
    if (Object.keys(v).includes('$$typeof')) {
      return v
    } else {
      return JSON.stringify(v)
    }
  } else {
    return v
  }
}

const Buttons = ({buttons, ctx}) => (
  buttons && <div className="text-right mb-2">
    <ButtonGroup className="btn-divider">
      {buttons.filter(b => b).map(b => (
        b.confirm_msg ?
          <ButtonConfirm key={b.name}
                         action={b.action}
                         modal_title={b.name}
                         btn_text={b.name}
                         redirect_to={b.redirect_to}
                         success_msg={b.success_msg}
                         done={b.done}
                         btn_color={b.btn_color}
                         btn_size="sm"
                         className="ml-2">
            {b.confirm_msg}
          </ButtonConfirm>
          :
          <Button key={b.name} tag={Link} to={b.link} disabled={b.disabled || false}>{b.name}</Button>
      ))}
    </ButtonGroup>
  </div>
)

export const Dash = () => <span>&mdash;</span>

export const Detail = ({name, wide, edit_link, children}) => (
  <div className={`item-detail${wide ? ' wide' : ''}`}>
    <div className="key">
      {name}
      {edit_link && <Button tag={Link} to={edit_link} size="sm" className="ml-2">
        <FontAwesomeIcon icon="pencil-alt" className="mr-1"/>
        Edit {name}
      </Button>}
    </div>
    <div className="value">
      {render(children)}
    </div>
  </div>
)

export class RenderItem extends React.Component {
  constructor (props) {
    super(props)
    this.render_key = this.render_key.bind(this)
    this.render_value = this.render_value.bind(this)
    this.update = this.update.bind(this)
    this.got_data = this.got_data.bind(this)
    this.get_uri = this.get_uri.bind(this)
  }

  get_uri () {
    return `/${this.props.page.name}/`
  }

  componentDidMount () {
    this.props.ctx.setRootState({
      page_title: as_title(this.props.page.name),
    })
    this.update()
  }

  componentDidUpdate (prevProps) {
    const l = this.props.location
    if (l.pathname + l.search !== prevProps.location.pathname + prevProps.location.search) {
      this.update()
    }
  }

  async update () {
    let data = null
    const uri = this.get_uri()
    try {
      data = await requests.get(uri)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.got_data(data)
  }

  async got_data (data) {
    this.setState(data)
  }

  render_key (key) {
    const fmt = this.state.formats[key]
    if (fmt && fmt.title) {
      return fmt.title
    }
    return as_title(key)
  }

  extra () {}

  render_value (item, key) {
    const fmt = this.state.formats[key]
    const v = item[key]
    if (fmt && fmt.render) {
      return fmt.render(v, item)
    } else {
      return render(v)
    }
  }
}


export class RenderList extends RenderItem {
  constructor (props) {
    super(props)
    this.state = {
      items: null,
      count: null,
      pages: null,
      buttons: null,
      formats: {},
    }
    this.get_page = this.get_page.bind(this)
  }

  get_page () {
    const m = this.props.location.search.match(/page=(\d+)/)
    return m ? parseInt(m[1]) : 1
  }

  get_uri () {
    return `/${this.props.page.name}/?page=${this.get_page()}`
  }

  get_link (item) {
    return `${item.id}/`
  }

  no_items_msg () {
    return `No ${as_title(this.props.page.name)} found`
  }

  render () {
    if (!this.state.items) {
      return <Loading/>
    } else if (this.state.items.length === 0) {
      return [
        <Buttons key="b" buttons={this.state.buttons}/>,
        <div key="f" className="text-muted text-center h5 mt-4">
          {this.no_items_msg()}
        </div>,
        <div key="e">
          {this.extra()}
        </div>
      ]
    }
    const keys = Object.keys(this.state.items[0])
    keys.includes('id') && keys.splice(keys.indexOf('id'), 1)
    const current_page = this.get_page()
    return [
      <Buttons key="b" buttons={this.state.buttons}/>,
      <table key="t" className="table dashboard">
        <thead>
          <tr>
            {keys.map((key, i) => (
              <th key={i} scope="col">{this.render_key(key)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {this.state.items.map((item, i) => (
            <tr key={i}>
              {keys.map((key, j) => (
                j === 0 ? (
                  <td key={j}>
                    <Link to={this.get_link(item)}>{this.render_value(item, key)}</Link>
                  </td>
                ) : (
                  <td key={j}>{this.render_value(item, key)}</td>
                )
              ))}
            </tr>
          ))}
        </tbody>
      </table>,
      this.state.pages > 1 ? (
        <nav key="p" aria-label="Page navigation example">
          <ul className="pagination justify-content-center">
            {[...Array(this.state.pages).keys()].map(i => i + 1).map(p => (
              <li key={p} className={'page-item' + (p === current_page ? ' active' : '')}>
                <Link className="page-link" to={`?page=${p}`}>{p}</Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null,
      <div key="e">
        {this.extra()}
      </div>
    ]
  }
}

export class RenderDetails extends RenderItem {
  constructor (props) {
    super(props)
    this.state = {
      formats: {},
      item: null,
      buttons: []
    }
    this.id = this.props.match.params.id
    this.pre = this.pre.bind(this)
  }

  get_uri () {
    return `/${this.props.page.name}/${this.id}/`
  }

  async got_data (data) {
    this.setState({item: data})
    this.props.ctx.setRootState({
      page_title: data.name || as_title(this.props.page.name),
    })
  }

  pre () {}

  render () {
    if (!this.state.item) {
      return <Loading/>
    }
    const keys = (
      Object.keys(this.state.item)
      .filter(k => !['id', '_response_status', 'name'].includes(k) && this.state.formats[k] !== null)
      .sort((a, b) => ((this.state.formats[a] || {}).wide || 0) - ((this.state.formats[b] || {}).wide || 0))
      .sort((a, b) => ((this.state.formats[a] || {}).index || 0) - ((this.state.formats[b] || {}).index || 0))
    )
    const pre = this.pre()
    return [
      <Buttons key="b" buttons={this.state.buttons}/>,
      this.state.item.name && <h1 key="t">{this.state.item.name}</h1>,
      pre ? <div key="p">{pre}</div> : null,
      <div key="d" className="mb-4">
        {keys.map(key => (
          <Detail key={key}
                  name={this.render_key(key)}
                  wide={Boolean((this.state.formats[key] || {}).wide)}
                  edit_link={(this.state.formats[key] || {}).edit_link}>
            {this.render_value(this.state.item, key)}
          </Detail>
        ))}
      </div>,
      <div key="e">
        {this.extra()}
      </div>,
    ]
  }
}

export const ImageThumbnail = ({image, alt, image_type}) => (
  image ?
    <img src={image_thumb(image, image_type)} alt={alt} className="img-thumbnail"/>
    :
    <span>&mdash;</span>
)

export const MiniMap = ({lat, lng, name}) => (
  <div>
    {name}
    <Map geolocation={{lat, lng, name}} height={200} width={400} className="rounded"><Dash/></Map>
  </div>
)


export const MarkdownPreview = ({v}) => (
  v ? <MarkdownRender className="dashboard-markdown" content={v}/> : <Dash/>
)
