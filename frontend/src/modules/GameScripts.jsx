import React, { Component } from 'react';
import { Button, Form, FormGroup, Label, Input, Table, Breadcrumb, 
  BreadcrumbItem, Pagination, PaginationItem, PaginationLink, 
  Container, Row, Col, UncontrolledTooltip } from 'reactstrap';
import qs from 'query-string';
import AsyncSelect from 'react-select/async';
import { isEqual, debounce } from 'lodash-es';
import Highlighter from 'react-highlight-words';
import { FaSortUp, FaSortDown, FaQuestionCircle } from 'react-icons/fa';
import { withRouter } from "react-router";
import { Link, useParams } from 'react-router-dom';
import SimpleLoadingBar from 'react-simple-loading-bar';
import NumberFormat from 'react-number-format';
import { json2csvAsync } from 'json-2-csv';

export default class GameScripts extends Component {

  constructor(props) {
    super(props);

    this.state = {...this.initState(), ...this.resetState()};

    this.fetchGames = this.fetchGames.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
    this.loadResults = this.loadResults.bind(this);
    this.updateStateFromQueryString = this.updateStateFromQueryString.bind(this);
    this.getStateFromQueryString = this.getStateFromQueryString.bind(this);
    this.setCurrentPage = this.setCurrentPage.bind(this);
    this.setCharactersLoading = this.setCharactersLoading.bind(this);
    this.updateField = this.updateField.bind(this);
    this.toggleStrictSearch = this.toggleStrictSearch.bind(this);
  }

  // reset whenever changing navigation
  resetState() {
    return {
      q: '',
      gameId: '',
      chr: [],
      fname: '',
      showPortraits: true,
      showEvoPortraits: false,
      currentPage: 1,
      strictSearch: false,
    }
  }

  // initial state which shouldn't be reset on navigation
  initState() {
    return {
      allGames: [],
      searchStats: [],
      numPages: 0,
      searchResults: undefined,
      scriptDetails: undefined,
    };
  }
  
  updateField(field, newValue) {
    this.setState({
      [field]: newValue
    })
  }

  setLoading(value) {
    this.setState({
      loading: value,
    });
  }

  setCharactersLoading(value) {
    this.setState({
      charactersLoading: value,
    });
  }

  componentDidMount() {
    console.log('componentDidMount');
    this.fetchGames().then(res => {
      this.loadResults(this.props);
    });
  }

  componentDidUpdate(prevProps) {
    // console.log('componentDidUpdate', prevProps);
    if (this.props.location.search != prevProps.location.search) {
      console.log('componentDidUpdate diff', this.props.location.search, prevProps.location.search);
      this.loadResults(this.props, prevProps);
    }
  }

  fetchScriptInfo() {
    return fetch(`/api/script/file/detail/?game_id=${encodeURIComponent(this.state.gameId)}&fname=${encodeURIComponent(this.state.fname)}`)
      .then(res => res.json())
      .then(res => {
        this.setState({
          scriptInfo: res,
        });
      });
  }

  fetchGames() {
    console.log('fetchGames');
    return fetch('/api/game/')
      .then(res => res.json())
      .then(res => {
        console.log('fetchGames res', res);
        this.setState({
          allGames: res,
        });
      });
  }

  fetchSearchStats(searchQueryString, callback) {
    return fetch(`/api/script/search/stat?${searchQueryString}`)
        .then(res => res.json())
        .then(res => {
          console.log('searchStats', res);
          return this.setState({
            searchStats: res,
          }, callback);
        });
  }

  setNumPages() {

    let numPages = 1;

    if (this.state.searchStats.length > 0) {
      if (this.state.gameId > 0) {
        // console.log(this.state.gameId, this.state.searchStats.findIndex( g => g.game?.id === this.state.gameId), this.state.searchStats)
        let index = this.state.searchStats.findIndex( g => g.game?.id === this.state.gameId);
        if (index !== -1) {
          numPages = Math.ceil(this.state.searchStats[this.state.searchStats.findIndex( g => g.game?.id === this.state.gameId)].rows / 100);
        } else {
          numPages = 0;
        }
      } else {
        numPages = Math.ceil(this.state.searchStats[this.state.searchStats.length - 1].rows / 100);
      }
    }

    this.setState({
      numPages: numPages,
    });
  }

  stateToQueryString() {
    let queryParams = {};
    if (this.state.q) {
      queryParams.q = this.state.q;
    }

    if (this.state.gameId) {
      queryParams.game_id = this.state.gameId;
    }

    if(this.state.chr) {
      queryParams['chr[]'] = this.state.chr.map(c => c.chr);
    }

    if (this.state.strictSearch) {
      queryParams.strict_search = 1;
    }

    return queryParams;
  }

  handleSubmit(e) {
    e.preventDefault();
    
    let queryParams = this.stateToQueryString();
    
    // fresh search - always set to page 1
    queryParams.p = 1;

    // triggers componentWillReceiveProps
    this.props.history.push({
      pathname: '/game-scripts',
      search: '?' + qs.stringify(queryParams)
    });
  }

  toggleStrictSearch() {
    this.setState({
      strictSearch: !this.state.strictSearch,
    });
  }

  setCurrentPage(page) {
    let queryParams = this.stateToQueryString();
    queryParams.p = page;

    // triggers componentWillReceiveProps
    this.props.history.push({
      pathname: '/game-scripts',
      search: '?' + qs.stringify(queryParams)
    });
  }

  getStateFromQueryString(props) {
    console.log('getStateFromQueryString');

    const params = props.location ? qs.parse(props.location.search) : {};

    let chr = [];

    if (Array.isArray(params['chr[]'])) {
      chr = params['chr[]'].map((chr_name) => ({chr: chr_name}));
    } else {
      if (params['chr[]']) {
        chr.push({chr: params['chr[]']});
      }
    }

    let newState = this.resetState();

    newState.chr = chr;

    if (params.q) {
      newState.q = params.q;
    }

    if (params.game_id) {
      let gameIdInt = parseInt(params.game_id);
      if (!isNaN(gameIdInt)) {
        newState.gameId = gameIdInt;
      }
    }

    if (params.fname) {
      newState.fname = params.fname;
    }

    if (params.p) {
      let page = parseInt(params.p);
      if (!isNaN(page)) {
        newState.currentPage = page;
      }
    }

    if (params.strict_search) {
      newState.strictSearch = params.strict_search === '1';
    }

    return newState;
  }

  updateStateFromQueryString(props, callback) {

    console.log("updateStateFromQueryString", props)
    return this.setState(this.getStateFromQueryString(props), callback);
  }

  loadSearchResults(props) {
    console.log('loadSearchResults');

    this.setState({
      loading: true
    });

    let url = '/api/script/search?';
    let params = {
      "chr[]": this.state.chr.map(c => c.chr)
    };

    let titleParts = [...params["chr[]"]];

    if (this.state.q) {
      titleParts.push(this.state.q);
      params.q = this.state.q;
    }

    if (titleParts.length > 0) {
      props.setTitleName(titleParts.join(', ') + ' - Trails in the Database'); 
    }

    if (this.state.strictSearch) {
      params.strict_search = 1;
    }

    let searchQueryString = qs.stringify(params);

    params.game_id = this.state.gameId;

    if (this.state.currentPage) {
      params.page_number = this.state.currentPage;
    }

    let gameIdQueryString = qs.stringify(params);

    console.log(gameIdQueryString)

    return fetch(url + gameIdQueryString)
      .then(res => res.json())
      .then(res => {

        let totalResults = 0;

        for (let key in res) {
          totalResults += res[key].length;
        }

        this.setState({
          searchResults: res,
          loading: false,
        });

        return searchQueryString;
      });
  }

  loadScriptDetails(props) {
    console.log('loadScriptDetails');
    props.setTitleName(this.state.gameId + '/' + this.state.fname + ' - Trails in the Database'); 
    this.setState({
      loading: true
    });
    fetch(`/api/script/detail/${encodeURIComponent(this.state.gameId)}/${encodeURIComponent(this.state.fname)}`)
      .then(res => res.json())
      .then(res => {
        this.setState({
          scriptDetails: res,
          loading: false
        });
      }).then(res => {
        this.fetchScriptInfo().then( x => {
          // this.fetchGames();
        });
      });
  }

  loadResults(props, prevProps) {

    console.log('loadResults: entering');

    // let oldQ = this.state.q;
    // let oldChr = [...this.state.chr];
    // console.log('oldQ', this.state.q);
    let oldState = {};
    if (prevProps) {
      oldState = this.getStateFromQueryString(prevProps);
    }

    // Initialize state from URL
    this.updateStateFromQueryString(props, () => {
      // Perform Search
      if (this.state.q || (this.state.chr && this.state.chr.length > 0)) {

        this.setState({
          scriptDetails: undefined, // reset script details
        })

        const reloadStats = this.state.q !== oldState.q || !isEqual(this.state.chr, oldState.chr) || this.state.strictSearch !== oldState.strictSearch;

        if (reloadStats) {
          this.setState({
            searchStats: [],
          })
        }

        this.loadSearchResults(props).then(searchQueryString => {
          // Only update search stats if the search actually changed
          // No need to update when changing page or game
          if (reloadStats) {
            this.fetchSearchStats(searchQueryString, this.setNumPages);
          } else {
            this.setNumPages();
          }
        });
        // Load Script Details
      } else if (this.state.fname && this.state.gameId) {
        this.setState({
          searchResults: undefined, // reset search results
        })
        this.loadScriptDetails(props);
      } else {
        this.setState({
          searchResults: undefined, // reset search results
          scriptDetails: undefined, // reset script details
        });
      }
    });
  }

  render() {
    return (
      <div className="container">
        <SimpleLoadingBar activeRequests={(this.state.loading || this.state.charactersLoading) ? 1 : 0} color="#007bff"></SimpleLoadingBar>
        <h2>Game Scripts</h2>
        <Breadcrumb>
          <BreadcrumbItem><Link to={'/game-scripts?='}>Scripts</Link></BreadcrumbItem>
          {this.state.gameId && this.state.gameId !== '0' && <BreadcrumbItem active={!this.state.fname}><Link to={`/game-scripts?game_id=${this.state.gameId}`}>{this.state.allGames.length > 0 && this.state.allGames[this.state.gameId - 1].titleEng}</Link></BreadcrumbItem>}
          {this.state.searchResults && <BreadcrumbItem active>Search Results</BreadcrumbItem>}
          {this.state.fname && <BreadcrumbItem active>{this.state.fname}</BreadcrumbItem>}
        </Breadcrumb>
        <Form inline onSubmit={this.handleSubmit}>
          <FormGroup className="mb-2 mr-sm-2 mb-sm-0">
            <Input type="select" name="game_id" id="game_id" value={this.state.gameId} onChange={(e) => this.updateField('gameId', e.target.value)} >
              <option value={0}>All Games</option>
              { this.state.allGames.map(game => 
                (<option key={game.id} value={game.id}>{game.titleEng}</option>)
              ) }
            </Input>
          </FormGroup>
          <FormGroup className="mb-2 mr-sm-2 mb-sm-0">
            <CharSelect onChange={(e) => this.updateField('chr', e)} value={this.state.chr} name="chr" allGames={this.state.allGames} />
          </FormGroup>
          <FormGroup className="mb-2 mr-sm-2 mb-sm-0">
            <Input type="text" name="q" id="queryText" placeholder="Enter English or Japanese Text..." value={this.state.q} onChange={(e) => this.updateField('q', e.target.value)} />
          </FormGroup>
          <FormGroup check className="mb-2 mr-sm-2 mb-sm-0">
            <Label check>
              <Input type="checkbox" name="strictSearch" id="matchCase" checked={this.state.strictSearch} onChange={(e) => this.toggleStrictSearch()} />
              Strict Search
            </Label>
            &nbsp;
            <FaQuestionCircle id="search-help" />
            <UncontrolledTooltip placement="top" target="search-help">
              <h6>Standard Search</h6>
              <p>The standard search finds all rows containing all of the words entered, ignoring letter case and punctuation. It also supports the following operators:</p>
                <ul>
                  <li>Use double quotation marks to search for a phrase.</li>
                  <li>Use the OR operator to search for one term or another term.</li>
                  <li>Put a hyphen character in front of a word to exclude that word from the search.</li>
                </ul>
              <p>These operators can be combined freely. For example: <code>cao -heiyue OR "the yin"</code></p>
              <p>This search is in active development and may contain bugs. Use the strict search if the standard search behaves unexpectedly.</p>
              <h6>Strict Search</h6>
              <p>Strict search simply performs a case-insensitive search for all rows which contain the input exactly as typed.</p>
            </UncontrolledTooltip>
          </FormGroup>
          <Button>Search</Button>
        </Form>
        <br/>


        {this.state.searchResults && 
        <SearchResults 
          gameId={this.state.gameId} 
          searchResults={this.state.searchResults} 
          allGames={this.state.allGames} 
          searchStats={this.state.searchStats} 
          showPortraits={this.state.showPortraits} 
          showEvoPortraits={this.state.showEvoPortraits} 
          q={this.state.q} 
          location={this.props.location}
          numPages={this.state.numPages} 
          currentPage={this.state.currentPage}
          setCurrentPage={this.setCurrentPage}
          updateField={this.updateField}
        />}
        {this.state.scriptDetails && 
        <ScriptDetails 
          gameId={this.state.gameId} 
          fname={this.state.fname} 
          scriptDetails={this.state.scriptDetails} 
          scriptInfo={this.state.scriptInfo} 
          showPortraits={this.state.showPortraits} 
          showEvoPortraits={this.state.showEvoPortraits} 
          updateField={this.updateField}
          loading={this.state.loading}
        />}

        { !this.state.searchResults && !this.state.scriptDetails && !this.state.loading && 
          <Container>
            <Row>
              <Col xs="auto">
                <ScriptBrowse allGames={this.state.allGames} gameId={this.state.gameId} />
               </Col>
               <Col xs="auto">
                <CharacterData allGames={this.state.allGames} gameId={this.state.gameId} setLoading={this.setCharactersLoading} />
               </Col>
            </Row>
          </Container>
        }
      </div>
    );
  }
}

class SearchResults extends Component {
  constructor(props) {
    super(props);
  }

  render() {
    return (
        <div>
          {/* Number of Results Table */}
          <h6>Filter Search by Game</h6>
          <table className="table table-sm small">
            <thead>
              <tr>
                <td>Game</td>
                <td style={{'textAlign':'right'}}>Rows</td>
              </tr>
            </thead>
            <tbody>
              {this.props.searchStats.map(stat => (
                
                  <tr key={`${stat.game?.id}-num_rows`}>
                    <td>
                      {( (!stat.game && (!this.props.gameId || this.props.gameId === "0")) || (stat.game?.id == this.props.gameId)) ? 
                        stat.game ? stat.game.titleEng : 'All Games'
                      :
                        <Link to={{
                          pathname: '/game-scripts',
                          search: `?${qs.stringify({ 
                            ...qs.parse(this.props.location.search),
                            game_id: stat.game?.id,
                            p: 1,
                          })}`
                        }}>{stat.game ? stat.game.titleEng : 'All Games'}</Link>
                      }
                     </td>
                    <td style={{'textAlign':'right'}}><NumberFormat value={stat.rows} displayType={'text'} thousandSeparator={true} /></td>
                  </tr>
                
              ))}
            </tbody>
          </table>
          {
            this.props.searchResults.length > 0 ?
            <React.Fragment>
              <Container>
                <Row>
                  <Col xs="auto">
                    <TablePagination page={this.props.currentPage} numPages={this.props.numPages} setPage={this.props.setCurrentPage} />
                  </Col>
                  <Col>
                  </Col>
                  <Col xs="auto">
                    <PortraitSelector 
                      updateField={this.props.updateField}
                      showPortraits={this.props.showPortraits}
                      showEvoPortraits={this.props.showEvoPortraits}
                    />
                  </Col>
                  <Col xs="auto">
                    
                  </Col>
                </Row>
              </Container>
              <table className="table">
                <tbody>
                  {this.props.searchResults.map((row, i, searchResults) =>
                  [ i === 0 || row.gameId !== searchResults[i - 1].gameId ? 
                    <tr key={row.gameId + '-' + 'header'}>
                      <td colSpan={7}><h4><a id={'game-' + row.gameId}>{this.props.allGames && this.props.allGames[row.gameId - 1] && 
                        (this.props.allGames[row.gameId - 1].titleEng + ' ・ ' + this.props.allGames[row.gameId - 1].titleJpnRoman + ' ・ ' + this.props.allGames[row.gameId - 1].titleJpn)
                      }</a></h4>
                      </td>
                    </tr>
                     : null,
                    <tr key={`${row['gameId']}-${row['fname']}-${row['row']}`}>
                      <td><Link to={{
                        pathname: '/game-scripts',
                        search: `?${qs.stringify({
                          game_id: row['gameId'], 
                          fname: row['fname']
                        })}`,
                        hash: `#${row['row']}`
                      }}>{row['fname']}</Link></td>
                      <td>{row['row']}</td>
                      {this.props.showPortraits && <td className="td-icon" dangerouslySetInnerHTML={{__html: this.props.showEvoPortraits && row['gameId'] < 4 ? row['evoIconHtml'] : row['pcIconHtml']}}></td> }
                      <td dangerouslySetInnerHTML={{__html:'<span class="chr-name">' + row['engChrName'] + '</span>' + row['engHtmlText']}}></td>
                      <td dangerouslySetInnerHTML={{__html:'<span class="chr-name">' + row['jpnChrName'] + '</span>' + row['jpnHtmlText']}}></td>
                    </tr>]
                    )}
                </tbody>
              </table>
              <TablePagination page={this.props.currentPage} numPages={this.props.numPages} setPage={this.props.setCurrentPage} />
            </React.Fragment> 
            :
            <p>
              {this.props.searchStats.length > 1 ? 
               `No results found in ${this.props.allGames[this.props.gameId - 1]?.titleEng}. Please filter on another game or try another search.`
                : 
               "No results found. Please try another search."}
            </p>
          }
        </div>
    );
  }
}

class ScriptDetails extends Component {
  constructor(props) {
    super(props);
  }

  componentDidMount() {
    console.log('ScriptDetails: componentDidMount');
    setTimeout(function () {
        let baseUrl = window.location.href.split('#')[0];
        let t = window.location.hash;
        window.history.replaceState(null,null,baseUrl);
        window.location.hash = t;
    }, 0);
  }

  handleExport() {

    this.props.updateField('loading', true);

    const url = `/api/script/detail/${encodeURIComponent(this.props.gameId)}/${encodeURIComponent(this.props.fname)}`;

    fetch(url)
    .then(res => res.json())
    .then(res => {
      json2csvAsync(res, {
        emptyFieldValue: '',
      })
        .then((csv) => {
          const blob = new Blob([csv], {type: 'text/csv'});
          const downloadUrl = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = downloadUrl;
          a.download = `${this.props.gameId}-${this.props.fname}.csv`;
          document.body.appendChild(a);
          this.props.updateField('loading', false);
          a.click();
          a.remove();
        });
    });
  }

  render() {

    let sceneNum = 1;

    let titles = [this.props.fname];
    let jpn_place_names = [''];
    let eng_place_names = [''];

    if (this.props.scriptInfo) {
      if (this.props.scriptInfo.eng_place_names) {
        // titles.push(this.props.scriptInfo.eng_place_names);
        eng_place_names = this.props.scriptInfo.eng_place_names.split(',');
      }

      if (this.props.scriptInfo.jpn_place_names) {
        // titles.push(this.props.scriptInfo.jpn_place_names);
        jpn_place_names = this.props.scriptInfo.jpn_place_names.split(','); 
      }
    }

    return (
      <div>
        <Container>
          <Row>
            <Col xs="auto">
              <h3>{titles.join('・')} <small>{this.props.scriptDetails.length} rows</small></h3>
              <h4>{eng_place_names[0]} <small>{eng_place_names.slice(1).join(' ・ ')}</small></h4>
              <h4>{jpn_place_names[0]} <small>{jpn_place_names.slice(1).join(' ・ ')}</small></h4>
            </Col>
            <Col>
            </Col>
            <Col xs="auto">
              { 
                this.props.gameId < 4 &&
                <PortraitSelector 
                  updateField={this.props.updateField}
                  showPortraits={this.props.showPortraits}
                  showEvoPortraits={this.props.showEvoPortraits}
                />
              }
            </Col>
            <Col xs="auto">
              <Button disabled={this.props.loading} onClick={() => this.handleExport()}>Export</Button>
            </Col>
          </Row>
        </Container>
        <table className="table">
          <tbody>
            {  
              this.props.scriptDetails.map((row, i) => 
              [(i == 0 || this.props.scriptDetails[i-1]['scene'] != row['scene']) && 
              <tr key={'scene-' + i}><th colSpan="4">Scene { sceneNum++ }<hr style={{float:'right'}}/></th></tr>, 
              <tr key={row['game_id'] + '-' + row['fname'] + '-' + row['row']}>
                <td><a id={row['row']}>{row['row']}</a></td>
                {this.props.showPortraits && <td className="td-icon" dangerouslySetInnerHTML={{__html:this.props.showEvoPortraits && row['gameId'] < 4 ? row['evoIconHtml'] : row['pcIconHtml']}}></td>}
                <td dangerouslySetInnerHTML={{__html:'<span class="chr-name">' + row['engChrName'] + '</span>' + row['engHtmlText']}}></td>
                <td dangerouslySetInnerHTML={{__html:'<span class="chr-name">' + row['jpnChrName'] + '</span>' + row['jpnHtmlText']}}></td>
              </tr>])}
          </tbody>
        </table>
      </div>
    );
  }
}

class CharSelect extends Component {

  constructor(props) {
    super(props);
  }

  filterColors = inputValue => {
    return this.state.allChars.filter(i =>
        i.eng_chr_name.toLowerCase().includes(inputValue.toLowerCase()) 
        || i.jpn_chr_name.toLowerCase().includes(inputValue.toLowerCase())
    );
  };

  promiseOptions = (inputValue, callback) => {
    const results = [];

    let url = '/api/chr/?chr=' + encodeURIComponent(inputValue);
    
    fetch(url)
      .then(res => res.json())
      .then(res => {
        for (let i = 0; i < res.length; i++) {
          if (res[i].engChrName) {
            results.push({
              game_id: res[i].gameId,
              chr: res[i].engChrName,
            });
          }
          if (res[i].jpnChrName) {
            results.push({
              game_id: res[i].gameId,
              chr: res[i].jpnChrName,
              is_jpn: true,
            });
          }
        }
        console.log(callback, results);
        callback(results);
      });
  };

  debouncedPromiseOptions = debounce(this.promiseOptions, 350);

  getOptions = (inputValue, callback) => {
    console.log('getOptions', inputValue);
    if (!inputValue || inputValue.trim().length === 0) {
      console.log('getOptions empty');
      return Promise.resolve([]);
    } 

    this.debouncedPromiseOptions(inputValue, callback);
  }

  render() {

    const customStyles = {
      control: (base) => ({
        ...base,
        padding:'0px',
        margin:'0px',
        width: 300,
      }),
  option: (provided, state) => ({
    ...provided,
    borderBottom: state.data.is_jpn ? '1px solid rgba(0,0,0,.1)' : '',
    borderTop: !state.data.is_jpn ? '1px solid rgba(0,0,0,.1)' : '',
  }),
    };

    return (
      <AsyncSelect
        className="basic-single"
        classNamePrefix="select"
        name={this.props.name}
        defaultOptions
        isClearable
        isMulti
        cacheOptions
        openMenuOnClick={false}
        loadOptions={this.getOptions}
        getOptionValue={({ chr }) => chr}
        value={this.props.value}
        onChange={this.props.onChange}
        onInputChange={(inputValue) => this._inputValue = inputValue}
        formatOptionLabel={(option, {context}) => (
          context === 'value' ? option.chr :
          <div style={{width:'100%'}} className={option.is_jpn ? '' : ''}>
            <Highlighter className="suggestion-org-text"
              searchWords={[this._inputValue]}
              textToHighlight={option.chr ? option.chr : ''}
              highlightClassName="suggestion-highlight"
            />
            <span style={{float:'right'}}>{option.game_id.map(id => this.props.allGames[id - 1] && 
              <span key={id} className="badge badge-primary" style={{margin:'0px 2px'}}>{this.props.allGames[id - 1].titleEng.slice(this.props.allGames[id - 1].titleEng.lastIndexOf(' ') + 1)}</span> )}</span>
          </div>
        )}
        styles={customStyles}
        placeholder="Select Character Names"
      />
    );
  }
}

const ScriptBrowse = props => {

  return (
    <div>
      <h3>Browse Script Files by Game</h3>
      {!props.gameId && <GameList {...props} />}
      {props.gameId && props.gameId !== '0' && <FileList {...props} />}
    </div>
  );
}

const GameList = props => {
  const columns = [
    {
      name: '#',
      key: 'id',
    }, 
    {
      name: 'Game',
      key: 'titleEng',
    },
    {
      name: 'Rows',
      key: 'rows',
    }
  ];

  return (
    <Table size="sm">
      <thead>
        <tr>
          {columns.map(col => <th key={col.key}>{col.name}</th>)}
        </tr>
      </thead>
      <tbody>
        {
          props.allGames.map(game => 
            <tr key={game.id}>
              <td>{game.id}</td>
              <td><Link to={'/game-scripts?game_id=' + encodeURIComponent(game.id)}>{game.titleEng}</Link></td>
              <td>{parseInt(game.rows).toLocaleString()}</td>
            </tr>
          )
        }
      </tbody>
    </Table>
  );  
}

const FileList = props => {

  const [files, setFiles] = React.useState([]);
  const [sortCol, setSortCol] = React.useState('fname');
  const [sortAsc, setSortAsc] = React.useState(1);


  React.useEffect(() => {

    const abortController = new AbortController();

    const fetchData = async () => {
      try {
        const ret = await fetch(`/api/file/?game_id=${props.gameId}`, {signal: abortController.signal});
        const data = await ret.json();

        for (let i = 0; i < data.length; i++) {
          if (data[i].engChrNames) {
            data[i].engChrNames = data[i].engChrNames.filter(name => name.trim().length > 0).join(', ');
          } else {
            data[i].engChrNames = '';
          }

          if (data[i].jpnChrNames) {
            data[i].jpnChrNames = data[i].jpnChrNames.filter(name => name.trim().length > 0).join('、');
          } else {
            data[i].jpnChrNames = '';
          }

          if (data[i].engPlaceNames) {
            data[i].engPlaceNames = data[i].engPlaceNames.filter(name => name.trim().length > 0).join(', ');
          } else {
            data[i].engPlaceNames = '';
          }
          
          if (data[i].jpnPlaceNames) {
            data[i].jpnPlaceNames = data[i].jpnPlaceNames.filter(name => name.trim().length > 0).join('、');          
          } else {
            data[i].jpnPlaceNames = '';
          }
        }      

        setFiles(data);
      } catch(e) {
        if (abortController.signal.aborted) {
          // cancelled
          console.log('cancelled')
        }

        console.log('aborted');
      }
    };

    fetchData();

    return () => {
      abortController.abort();
    }

  }, [props.gameId]);

  function sortFiles(newSortCol) {

    console.log(files)

    let newSortAsc = 1;

    if (sortCol === newSortCol) {
      newSortAsc = sortAsc * -1;
    }

    let newFiles = [...files].sort((a, b) => (typeof(a[newSortCol]) === 'number' ? a[newSortCol] - b[newSortCol] : a[newSortCol].localeCompare(b[newSortCol])) * newSortAsc);

    setSortCol(newSortCol);
    setFiles(newFiles);
    setSortAsc(newSortAsc);
  }

  const headers = [
    {
      key: 'fname',
      text: 'Filename',
      sortable: true
    },
    {
      key: 'rows',
      text: 'Rows',
      sortable: true,
    },
    {
      key: 'engPlaceNames',
      text: 'Place',
      sortable: true
    },
    {
      key: 'engChrNames',
      text: 'Characters',
      sortable: false
    },
    {
      key: 'jpnPlaceNames',
      text: '場所',
      sortable: true
    },
    {
      key: 'jpnChrNames',
      text: '人物',
      sortable: false
    }
  ];

  return (
    <div>
      <h4>{props.allGames && props.allGames.length > 0 && props.allGames[props.gameId - 1].titleEng + ' ・ ' + props.allGames[props.gameId - 1].titleJpnRoman + ' ・ ' + props.allGames[props.gameId - 1].titleJpn}</h4>
      <Table size="sm" hover striped>
        <thead>
          <tr>
            <th>#</th>
            {headers.map(col => <th key={col.key} onClick={() => col.sortable && sortFiles(col.key)}>{col.text} {col.sortable && sortCol === col.key && (sortAsc === 1 && <FaSortUp /> || sortAsc === -1 && <FaSortDown />)}</th>)}
          </tr>
        </thead>
        <tbody>
          {files.map((file, i) => <tr key={file.fname}>
            <td>{i + 1}</td>
            <td><Link to={{
              pathname: '/game-scripts',
              search: `?game_id=${encodeURIComponent(props.gameId)}&fname=${encodeURIComponent(file.fname)}`
            }}>
              {file.fname}
            </Link></td>
            <td>{parseInt(file.rows).toLocaleString()}</td>
            <td>{file.engPlaceNames}</td>
            <td>{file.engChrNames}</td>
            <td>{file.jpnPlaceNames}</td>
            <td>{file.jpnChrNames}</td>
          </tr>)}
        </tbody>
      </Table>
    </div>
  );
}

const CharacterData = props => {

  const [characters, setCharacters] = React.useState([]);
  const [chrCount, setChrCount] = React.useState(0);
  const [sortCol, setSortCol] = React.useState('rows');
  const [sortAsc, setSortAsc] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [numPages, setNumPages] = React.useState(0);
  const ROWS_PER_PAGE = 10;

  React.useEffect(() => {

    console.log('useEffect', page, sortAsc, sortCol, props.gameId);
    // setCharacters([]);
    props.setLoading(true);

    const abortController = new AbortController();

    const fetchData = async () => {
      try {

        let endpoint = `/api/chr/detail/?page_number=${page}&page_size=${ROWS_PER_PAGE}&sort=${sortCol}&asc=${sortAsc}`;

        if (props.gameId) {
          endpoint += `&game_id=${props.gameId}`;
        }

        const ret = await fetch(endpoint, {signal: abortController.signal});
        const data = await ret.json();  

        setCharacters(data);
        props.setLoading(false);
        // setChrCount(data.count); TODO separate call
      } catch(e) {
        if (abortController.signal.aborted) {
          // cancelled
          console.log('cancelled')
        }

        console.log('aborted');
        props.setLoading(false);
      }
    };

    fetchData();

    return () => {
      abortController.abort();
    }

  }, [page, sortAsc, sortCol, props.gameId]);
  // }, []);

  React.useEffect(() => {

    // setCharacters([]);

    const chrCountAbortController = new AbortController();

    const fetchChrCount = async () => {
      try {
        let endpoint = '/api/chr/detail/stat';

        if (props.gameId) {
          endpoint += `?game_id=${props.gameId}`;
        }

        const ret = await fetch(endpoint, {signal: chrCountAbortController.signal});
        const data = await ret.json();  

        setChrCount(data.rows);
      } catch (e) {
        if (chrCountAbortController.signal.aborted) {
          
        }
      }
    }

    fetchChrCount();

    return () => {
      chrCountAbortController.abort();
    }

  }, [props.gameId]);

  React.useEffect(() => {
    setNumPages(Math.ceil(chrCount / ROWS_PER_PAGE));
  }, [chrCount, ROWS_PER_PAGE]);

  function sortCharacters(newSortCol) {

    let newSortAsc = 1;

    if (sortCol === newSortCol) {
      newSortAsc = 1 - sortAsc;
    }

    // let newChars = [...characters].sort((a, b) => (typeof(a[newSortCol]) === 'number' ? a[newSortCol] - b[newSortCol] : a[newSortCol].localeCompare(b[newSortCol])) * newSortAsc);

    setSortCol(newSortCol);
    // setCharacters(newChars);
    setSortAsc(newSortAsc);
  }

  const headers = [
    {
      key: 'engChrName',
      text: 'Character',
      sortable: true,
      visible: true,
    },
    {
      key: 'jpnChrName',
      text: '人物',
      sortable: true,
      visible: true,
    },
    {
      key: 'gameId',
      text: 'Games',
      sortable: false,
      visible: !props.gameId 
    },
    {
      key: 'rows',
      text: 'Rows',
      sortable: true,
      visible: true
    }
  ];

  return (
    <div>
      <h3>Characters by Script Line Count</h3>
      <h4>{props.gameId && props.gameId !== '0' && props.allGames && props.allGames.length > 0 && props.allGames[props.gameId - 1].titleEng + ' ・ ' + props.allGames[props.gameId - 1].titleJpnRoman + ' ・ ' + props.allGames[props.gameId - 1].titleJpn}</h4>
      <Table size="sm" hover striped>
        <thead>
          <tr>
            <th>#</th>
            {headers.filter(col => col.visible).map(col => <th key={col.key} onClick={() => col.sortable && sortCharacters(col.key)}>{col.text} {col.sortable && sortCol === col.key && (sortAsc === 1 && <FaSortUp /> || sortAsc === 0 && <FaSortDown />)}</th>)}
          </tr>
        </thead>
        <tbody>
          {characters.map((chr, i) => <tr key={chr.engChrName+'-'+chr.jpnChrName}>
            <td>{(page-1) * ROWS_PER_PAGE + i + 1}</td>
            <td>{chr.engChrName ||               
              <React.Fragment>
                {'(Blank) '}
                <FaQuestionCircle id="blank-character" />
                <UncontrolledTooltip placement="top" target="blank-character">
                  This refers to lines of dialogue which don't contain a speaker, such as narration, treature chest quotes, and so on.
                </UncontrolledTooltip>
              </React.Fragment>
            }</td>
            <td>{chr.jpnChrName || '（無し）'}</td>
            {
              !props.gameId &&
              <td>{
                chr.gameId.map(id => props.allGames && props.allGames[id - 1] && 
                <span key={id} className="badge badge-primary" style={{margin:'0px 2px'}}>{props.allGames[id - 1].titleEng.slice(props.allGames[id - 1].titleEng.lastIndexOf(' ') + 1)}</span> )
              }</td>
            }
            <td>{parseInt(chr.rows).toLocaleString()}</td>
          </tr>)}
        </tbody>
      </Table>
      <TablePagination page={page} numPages={numPages} setPage={setPage} />
    </div>
  );
}

const TablePagination = ({page, numPages, setPage}) => {

  const [pages, setPages] = React.useState([]);

  React.useEffect(() => {
    if (numPages > 0) {
      let pages = [];

      for (let i = 1; i <= Math.min(3, numPages); i++) {
        pages.push(i);
      }
      
      for (let i = page - 3; i <= page + 3; i++) {
        if (i > 3 && i < numPages - 2) {
          pages.push(i);
        }
      }

      for (let i = numPages - 2; i <= numPages; i++) {
        if (i > 3) {
          pages.push(i);
        }
      }

      setPages(pages);
    }
  }, [numPages, page]);

  return (
      
        numPages > 0 &&
        <Pagination aria-label="Page">
          <PaginationItem disabled={page==1}>
            <PaginationLink previous onClick={() => setPage(page - 1)} />
          </PaginationItem>

          {pages.map((e, i) => 
            [(i > 0 && e - pages[i-1] != 1) && 
              <PaginationItem key={'gap-'+e} disabled>
                <PaginationLink>
                  ...
                </PaginationLink>
              </PaginationItem>
            ,
            
              <PaginationItem key={i} active={page==e}>
                <PaginationLink onClick={() => setPage(e)}>
                  {e}
                </PaginationLink>
              </PaginationItem>]
            
          )}

          <PaginationItem disabled={page==numPages}>
            <PaginationLink next onClick={() => setPage(page + 1)} />
          </PaginationItem>
        </Pagination>
      
    );
}

const PortraitSelector = props => {
  return (
    <Form inline key="portraits-form">
      <FormGroup>
        <FormGroup check>
          <Label check>
            <Input type="radio" name="portraits"  onChange={(e) => {props.updateField('showPortraits', true); props.updateField('showEvoPortraits',false)}} value={false} checked={props.showPortraits === true && props.showEvoPortraits === false} />{' '}
            Original &nbsp;
          </Label>
        </FormGroup>

        <FormGroup check>
          <Label check>
            <Input type="radio" name="portraits"  onChange={(e) => {props.updateField('showPortraits', true); props.updateField('showEvoPortraits',true)}} value={true} checked={props.showPortraits === true && props.showEvoPortraits === true} />{' '}
            Evo &nbsp;
          </Label>
        </FormGroup>

        <FormGroup check>
          <Label check>
            <Input type="radio" name="portraits"  onChange={(e) => props.updateField('showPortraits',false)} value={true} checked={props.showPortraits === false} />{' '}
            No Portraits
          </Label>
        </FormGroup>
      </FormGroup>
    </Form>
  );
}